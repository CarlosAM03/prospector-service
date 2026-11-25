import asyncio
import sys
from collections import Counter

import pytest

from prospector_service import runner as runtime
from prospector_service.runner import ProcessRunner

from .conftest import batch, post, session, status, until

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        sys.platform != "linux", reason="ProcessRunner and pidfd supervision target Linux"
    ),
]


class FakeProcessRunner(ProcessRunner):
    def __init__(self, settings, gate, mode="cooperative"):
        super().__init__(settings)
        self.gate = gate
        self.mode = mode

    def command(self):
        return (
            sys.executable,
            "-m",
            "tests.fake_worker",
            str(self.settings.ipc_max_bytes),
            str(self.gate),
            self.mode,
            self.settings.prospector_chromium_sandbox,
        )


async def test_25_isolated_linux_workers(settings, tmp_path, monkeypatch):
    for name in ("INTERNAL_API_KEY", "CALLBACK_API_KEY", "ASSERTION_KEY", "METADATA_KEY"):
        monkeypatch.setenv(name, "env-must-not-reach-worker")
        monkeypatch.setenv(f"{name}_FILE", "path-must-not-reach-worker")
    monkeypatch.setenv("PROSPECTOR_CHROMIUM_SANDBOX", "0")
    settings = settings.model_copy(update={"prospector_chromium_sandbox": "1"})
    gate = tmp_path / "start"
    runner = FakeProcessRunner(settings, gate)
    if not runner.supported:
        pytest.skip("host cannot verify process cleanup")
    async with session(settings, runner) as (client, coord, _):
        fixtures = [(batch(i + 1), i // 5 + 1, i % 5 + 1) for i in range(25)]
        responses = await asyncio.gather(
            *(
                post(client, settings, item, tenant=tenant, owner=owner)
                for item, tenant, owner in fixtures
            )
        )
        assert all(response.status_code == 202 for response in responses)

        def counts():
            return Counter(
                dict(coord.store.db.execute("SELECT status, count(*) FROM jobs GROUP BY status"))
            )

        try:
            await until(lambda: counts()["RUNNING"] == 25, timeout=35)
            assert counts() == {"RUNNING": 25, "QUEUED": 100}
            assert (await client.get("/health/ready")).status_code == 200
        finally:
            gate.touch()
        await until(lambda: not coord.lanes, timeout=35)
        assert not coord.unsafe
        assert counts() == {"COMPLETED": 125}


async def test_worker_timeout_cooperative_and_verified(settings, tmp_path, monkeypatch):
    runner = FakeProcessRunner(settings, tmp_path / "never-start")
    if not runner.supported:
        pytest.skip("host cannot verify process cleanup")
    monkeypatch.setattr(runtime, "RUN_TIMEOUT", 0.3)
    payload = batch(count=2)
    async with session(settings, runner) as (client, coord, _):
        assert (await post(client, settings, payload)).status_code == 202
        await until(lambda: not coord.lanes, timeout=20)
        state = (await status(client, settings, payload)).json()["data"]
        assert [job["status"] for job in state["jobs"]] == ["INTERRUPTED", "SKIPPED"]
        assert state["jobs"][0]["errorCode"] == "BATCH_TIMEOUT"
        assert not state["active"] and not coord.unsafe


async def test_worker_timeout_kills_detached_child(settings, tmp_path, monkeypatch):
    runner = FakeProcessRunner(settings, tmp_path / "never-start", "wedged")
    if not runner.supported:
        pytest.skip("host cannot verify process cleanup")
    monkeypatch.setattr(runtime, "RUN_TIMEOUT", 0.4)
    monkeypatch.setattr(runtime, "CANCEL_GRACE", 0.3)
    monkeypatch.setattr(runtime, "TERMINATE_GRACE", 8)
    payload = batch(count=2)
    async with session(settings, runner) as (client, coord, _):
        assert (await post(client, settings, payload)).status_code == 202
        await until(lambda: not coord.lanes, timeout=20)
        state = (await status(client, settings, payload)).json()["data"]
        assert state["jobs"][0]["errorCode"] == "BATCH_TIMEOUT"
        assert [job["status"] for job in state["jobs"]] == ["INTERRUPTED", "SKIPPED"]
        assert not state["active"] and not coord.unsafe


async def test_same_uid_can_access_fixture_credential_and_sqlite(settings, tmp_path):
    gate = tmp_path / "released"
    gate.touch()
    fixture = tmp_path / "credential-fixture"
    fixture.write_text("synthetic-read-probe")
    fixture.chmod(0o400)
    runner = FakeProcessRunner(settings, gate, "acl_probe")
    if not runner.supported:
        pytest.skip("host cannot verify Linux worker access")
    payload = batch(count=1)
    async with session(settings, runner) as (client, coord, _):
        assert (await post(client, settings, payload)).status_code == 202
        await until(lambda: not coord.lanes, timeout=20)
        job = (await status(client, settings, payload)).json()["data"]["jobs"][0]
        assert job["status"] == "COMPLETED"
