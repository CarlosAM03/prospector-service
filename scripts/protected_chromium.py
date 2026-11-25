"""Run one sandbox-requested Chromium lane per verified lab profile, without network."""

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

PROFILE_URL = "https://api.github.com/repos/microsoft/playwright/git/blobs/fddc05fb520affb145404e6f6f647ca96af8087d"
PROFILE_HASH = "cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849"
ROOT = Path(__file__).resolve().parents[1]


def profiles(directory):
    with urlopen(PROFILE_URL, timeout=20) as response:
        content = base64.b64decode(json.load(response)["content"])
    if hashlib.sha256(content).hexdigest() != PROFILE_HASH:
        raise ValueError("Playwright seccomp profile hash mismatch")
    upstream = directory / "playwright-seccomp.json"
    upstream.write_bytes(content)
    profile = json.loads(content)
    profile["syscalls"].append(
        {
            "names": ["chroot"],
            "action": "SCMP_ACT_ALLOW",
            "args": [],
            "includes": {},
            "excludes": {},
        }
    )
    candidate = directory / "playwright-seccomp-chroot.json"
    candidate.write_text(json.dumps(profile), encoding="utf-8")
    profile["syscalls"].append(
        {
            "names": ["pidfd_open", "pidfd_send_signal"],
            "action": "SCMP_ACT_ALLOW",
            "args": [],
            "includes": {},
            "excludes": {},
        }
    )
    service = directory / "service-seccomp-lab.json"
    service.write_text(json.dumps(profile), encoding="utf-8")
    return [
        ("docker-default", None, True),
        ("playwright-upstream", upstream, False),
        ("playwright-chroot-lab", candidate, False),
        ("service-pidfd-lab", service, True),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="prospector-service:ci")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    info = subprocess.check_output(
        ["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"], text=True, timeout=15
    )
    cpus, memory = map(int, info.split())
    disk = shutil.disk_usage(ROOT).free
    print(f"PROTECTED_LAB_PREFLIGHT cpus={cpus} memory={memory} disk={disk}", flush=True)
    if cpus < 2 or memory < 3 * 1024**3 or disk < 2 * 1024**3:
        raise SystemExit("NOT_RUN: protected Chromium lab resources below preflight")

    args.output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="prospector-lab-") as scratch:
        directory = Path(scratch)
        for name, profile, integrated in profiles(directory):
            container = f"prospector-protected-{uuid4().hex[:12]}"
            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                container,
                "--init",
                "--network",
                "none",
                "--read-only",
                "--cpus=2",
                "--memory=2g",
                "--memory-swap=2g",
                "--pids-limit=256",
                "--shm-size=1g",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--ulimit",
                "core=0",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=512m,mode=1777",
                "-e",
                "PYTHONPATH=/gate",
                "-e",
                "PROSPECTOR_CHROMIUM_SANDBOX=1",
                "--mount",
                f"type=bind,source={ROOT / 'scripts'},target=/gate/scripts,readonly",
                "-w",
                "/gate",
            ]
            if profile:
                command += ["--security-opt", f"seccomp={profile}"]
            extra = ["--max-lanes", "1"] if integrated else ["--probe-only"]
            try:
                result = subprocess.run(
                    [
                        *command,
                        args.image,
                        "python",
                        "-m",
                        "scripts.benchmark_chromium",
                        "--protected",
                        *extra,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=270,
                )
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "rm", "-f", container], timeout=20, capture_output=True)
                outcomes.append(
                    {
                        "profile": name,
                        "scope": "service" if integrated else "engine",
                        "status": "FAIL",
                        "reason": "LAB_TIMEOUT",
                        "stages": [],
                    }
                )
                print(f"PROTECTED_PROFILE_TIMEOUT {name}", flush=True)
                break
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
            row = {
                "profile": name,
                "scope": "service" if integrated else "engine",
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "exit": result.returncode,
                "stages": rows,
            }
            if profile:
                row["profile_sha256"] = hashlib.sha256(profile.read_bytes()).hexdigest()
            outcomes.append(row)
            print("PROTECTED_PROFILE " + json.dumps(row, separators=(",", ":")), flush=True)
            if not rows and result.stderr:
                print(result.stderr, flush=True)
    (args.output / "chromium-protected.json").write_text(
        json.dumps(
            {
                "host": {"cpus": cpus, "memory_bytes": memory, "free_bytes": disk},
                "profiles": outcomes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return int(not any(row["status"] == "PASS" and row["scope"] == "service" for row in outcomes))


if __name__ == "__main__":
    raise SystemExit(main())
