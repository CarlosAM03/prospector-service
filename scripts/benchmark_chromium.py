"""Offline Linux benchmark using the real batch adapter and controlled Chromium acquisition."""

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import os
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx

from prospector_service.config import Settings
from prospector_service.main import create_app
from prospector_service.process_tree import descendants, process_table
from prospector_service.runner import ProcessRunner

BASE = "/api/v1/prospecting/batches"
SCALES = (1, 2, 3, 5, 10, 15, 20, 25)


def verify_lab_isolation():
    import resource

    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert os.getuid() == os.getgid() == 10001
    assert status["Seccomp"].strip() == "2"
    assert status["NoNewPrivs"].strip() == "1"
    assert not int(status["CapEff"].strip(), 16)
    assert {item.name for item in Path("/sys/class/net").iterdir()} == {"lo"}
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    assert Path("/sys/fs/cgroup/memory.swap.max").read_text().strip() == "0"
    mounts = [line.split() for line in Path("/proc/self/mountinfo").read_text().splitlines()]
    assert any(row[4] == "/" and "ro" in row[5].split(",") for row in mounts)
    assert any(
        row[4] == "/tmp"
        and row[row.index("-") + 1] == "tmpfs"
        and {"nosuid", "nodev"} <= set(row[5].split(","))
        for row in mounts
    )


def verify_browser_flags():
    commands = []
    for pid in descendants(os.getpid(), process_table()):
        try:
            command = Path("/proc", str(pid), "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"--remote-debugging-pipe" in command and b"chrome" in command[0]:
            commands.append(command)
    assert commands and all(b"--no-sandbox" not in command for command in commands)


def probe_protected_browser():
    from prospector_engine.browser import BrowserRuntime

    baseline = descendants(os.getpid(), process_table())
    with BrowserRuntime(headless=True, channel=None) as runtime:
        page = runtime.new_page()
        page.set_content("<title>protected browser probe</title>")
        assert page.title() == "protected browser probe"
        verify_browser_flags()
    assert page.is_closed()
    deadline = time.monotonic() + 3
    while descendants(os.getpid(), process_table()) - baseline and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not descendants(os.getpid(), process_table()) - baseline
    print("PROTECTED_BROWSER_PROBE_PASS")


def controlled_execute(batch, browser, headless, token, send):
    from prospector_engine import Business, SourceIdentityEvidence
    from prospector_engine.browser import BrowserRuntime
    from prospector_engine.engines import prospector_engine as implementation

    from prospector_service.adapters.engine import execute_batch

    def source(request, limit, **options):
        with BrowserRuntime(headless=True, channel=None) as runtime:
            page = runtime.new_page()
            page.set_content("<html><title>controlled benchmark</title></html>")
            assert page.title() == "controlled benchmark"
            if os.environ["PROSPECTOR_CHROMIUM_SANDBOX"] == "1":
                verify_browser_flags()
            time.sleep(0.35)
        return SimpleNamespace(
            query=request,
            businesses=[Business(f"Synthetic fixture {i}") for i in range(limit)],
            issues=[],
            identities=[SourceIdentityEvidence.unverified() for _ in range(limit)],
        )

    implementation._run_google_maps = source
    execute_batch(batch, browser, headless, token, send)


class ControlledRunner(ProcessRunner):
    def command(self):
        return sys.executable, "-m", "scripts.benchmark_chromium", str(self.settings.ipc_max_bytes)


def cuid(number):
    return f"c{number:024d}"


def signed(settings, body, tenant, owner, key):
    now = int(time.time())
    claims = {
        "iss": settings.assertion_issuer,
        "aud": settings.assertion_audience,
        "solutionId": settings.solution_id,
        "tenantId": tenant,
        "sub": owner,
        "scope": "prospecting:batches:create",
        "actorType": "owner",
        "iat": now,
        "exp": now + 90,
        "method": "POST",
        "path": BASE,
        "query": "",
        "bodySha256": hashlib.sha256(body).hexdigest(),
        "idempotencyKey": key,
    }

    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    unsigned = encode(b'{"alg":"HS256","typ":"JWT"}') + b"." + encode(json.dumps(claims).encode())
    signature = hmac.digest(settings.assertion_key.get_secret_value().encode(), unsigned, "sha256")
    return {
        "X-API-Key": settings.internal_api_key.get_secret_value(),
        "X-Platform-Assertion": (unsigned + b"." + encode(signature)).decode(),
        "Idempotency-Key": key,
        "Content-Type": "application/json",
    }


def process_sample(cpu_ticks):
    pids = descendants(os.getpid(), process_table())
    rss = pss = fds = browsers = 0
    for pid in pids | {os.getpid()}:
        path = Path("/proc", str(pid))
        try:
            args = (path / "cmdline").read_bytes().split(b"\0")
            if args and b"chrome" in args[0] and b"--remote-debugging-pipe" in args:
                browsers += 1
            stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
            cpu_ticks[(pid, stat[19])] = int(stat[11]) + int(stat[12])
            fds += len(list((path / "fd").iterdir()))
            rollup = (path / "smaps_rollup").read_text()
            parts = {
                line.split(":")[0]: line.split()[1]
                for line in rollup.splitlines()
                if line.startswith(("Rss:", "Pss:"))
            }
            rss += int(parts.get("Rss", 0))
            pss += int(parts.get("Pss", 0))
        except (OSError, ValueError, IndexError):
            continue
    shm = os.statvfs("/dev/shm")
    memory = Path("/sys/fs/cgroup/memory.current")
    return {
        "descendant_pids": len(pids),
        "browser_main_pids": browsers,
        "fds": fds,
        "rss_kib": rss,
        "pss_kib": pss,
        "shm_bytes": (shm.f_blocks - shm.f_bavail) * shm.f_frsize,
        "shm_capacity_bytes": shm.f_blocks * shm.f_frsize,
        "cgroup_memory_bytes": int(memory.read_text()) if memory.is_file() else 0,
    }


async def wave(lanes, directory, *, protected):
    events = []
    acceptance = []
    cpu_ticks = {}
    peaks = {}

    async def callback(request):
        payload = json.loads(request.content)
        events.append((payload, datetime.now(timezone.utc)))
        return httpx.Response(204)

    settings = Settings(
        app_env="test",
        metadata_path=directory / f"{lanes}.sqlite3",
        worker_temp_dir=Path("/tmp" if protected else "/dev/shm"),
        prospector_chromium_sandbox="1" if protected else "0",
        internal_api_key="a" * 32,
        assertion_key="b" * 32,
        metadata_key="c" * 32,
        callback_api_key="d" * 32,
        platform_callback_origin="https://benchmark.invalid",
    )
    runner = ControlledRunner(settings)
    if not runner.supported:
        raise RuntimeError("benchmark requires Linux pidfd and volatile /dev/shm")
    application = create_app(
        settings, runner=runner, callback_transport=httpx.MockTransport(callback)
    )

    async def monitor():
        while True:
            sample = await asyncio.to_thread(process_sample, cpu_ticks)
            for name, value in sample.items():
                peaks[name] = max(peaks.get(name, 0), value)
            await asyncio.sleep(0.15)

    async def submit(client, ordinal):
        bid = cuid(ordinal)
        body = json.dumps(
            {
                "batchId": bid,
                "jobs": [
                    {
                        "jobId": cuid(ordinal * 10 + j),
                        "query": {
                            "keyword": "synthetic",
                            "location": "controlled",
                            "source": "google_maps",
                            "limit": 150,
                        },
                    }
                    for j in range(5)
                ],
            }
        ).encode()
        headers = signed(
            settings, body, cuid((ordinal - 1) // 5 + 1), cuid((ordinal - 1) % 5 + 1), bid
        )
        began = time.monotonic()
        result = await client.post(BASE, content=body, headers=headers)
        acceptance.append(1000 * (time.monotonic() - began))
        return result.status_code

    began = time.monotonic()
    monitor_task = asyncio.create_task(monitor())
    timed_out = False
    try:
        async with application.router.lifespan_context(application):
            coord = application.state.coordinator
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url="http://benchmark"
            ) as client:
                codes = await asyncio.gather(*(submit(client, i + 1) for i in range(lanes)))
                try:
                    async with asyncio.timeout(180):
                        while coord.lanes or coord.relay.tasks:
                            await asyncio.sleep(0.05)
                except TimeoutError:
                    timed_out = True
            terminal = [event for event, _ in events if event["kind"] == "TERMINAL"]
            success = [
                event
                for event in terminal
                if event["status"] == "COMPLETED" and event.get("availability") == "AVAILABLE"
            ]
            lag = [
                (received - datetime.fromisoformat(event["timestamp"])).total_seconds() * 1000
                for event, received in events
                if event["kind"] == "PROGRESS"
            ]
            unsafe = coord.unsafe
    finally:
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
    duration = time.monotonic() - began
    cleanup = process_sample(cpu_ticks)
    cpu_seconds = sum(cpu_ticks.values()) / os.sysconf("SC_CLK_TCK")
    memory_limit_file = Path("/sys/fs/cgroup/memory.max")
    memory_limit = memory_limit_file.read_text().strip() if memory_limit_file.is_file() else "max"
    memory_ok = memory_limit == "max" or peaks.get("cgroup_memory_bytes", 0) < 0.75 * int(
        memory_limit
    )
    shm_ok = peaks.get("shm_bytes", 0) < 0.75 * peaks.get("shm_capacity_bytes", 1)
    outcome = (
        not timed_out
        and codes == [202] * lanes
        and len(success) == lanes * 5
        and bool(lag)
        and not unsafe
        and not cleanup["descendant_pids"]
        and memory_ok
        and shm_ok
        and peaks.get("browser_main_pids", 0) >= 1
    )
    return {
        "lanes": lanes,
        "status": "PASS" if outcome else "FAIL",
        "sandbox_requested": protected,
        "workload": "controlled Chromium acquisition, five queries, 150 synthetic rows per query",
        "accepted": codes.count(202),
        "completed_with_snapshots": len(success),
        "duration_seconds": round(duration, 3),
        "sampled_cpu_seconds": round(cpu_seconds, 3),
        "sampled_mean_cpu_cores": round(cpu_seconds / duration, 3),
        "ack_ms_median": round(statistics.median(acceptance), 3),
        "ack_ms_max": round(max(acceptance), 3),
        "progress_lag_ms_max": round(max(lag), 3) if lag else None,
        "peak_sample": peaks,
        "descendant_pids_after": cleanup["descendant_pids"],
        "cgroup_memory_limit": memory_limit,
        "worker_cleanup_unverified": unsafe,
        "wave_timeout": timed_out,
        "terminal_error_codes": sorted(
            {event["error"]["code"] for event in terminal if event.get("error")}
        ),
    }


async def benchmark(max_lanes, *, protected):
    if protected:
        assert os.environ.get("PROSPECTOR_CHROMIUM_SANDBOX") == "1"
        verify_lab_isolation()
    failed = False
    with tempfile.TemporaryDirectory(prefix="prospector-bench-", dir="/dev/shm") as path:
        for lanes in SCALES:
            if failed or lanes > max_lanes:
                print(json.dumps({"lanes": lanes, "status": "NOT_RUN"}), flush=True)
                continue
            try:
                result = await wave(lanes, Path(path), protected=protected)
            except Exception as exc:
                result = {"lanes": lanes, "status": "FAIL", "error_type": type(exc).__name__}
            print(json.dumps(result), flush=True)
            failed = result["status"] == "FAIL"
    return int(failed)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        from prospector_service.worker import main

        main(controlled_execute)
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--max-lanes", type=int, choices=SCALES, default=1)
        parser.add_argument("--protected", action="store_true")
        parser.add_argument("--probe-only", action="store_true")
        options = parser.parse_args()
        if options.probe_only:
            if not options.protected or os.environ.get("PROSPECTOR_CHROMIUM_SANDBOX") != "1":
                parser.error("the probe requires the protected profile")
            verify_lab_isolation()
            probe_protected_browser()
            sys.exit(0)
        sys.exit(asyncio.run(benchmark(options.max_lanes, protected=options.protected)))
