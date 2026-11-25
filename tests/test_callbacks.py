import asyncio
import json

import httpx

from .conftest import FakeRunner, batch, job_request, post, session, status, until


async def test_live_progress_retry_and_independent_lane(settings):
    pending = asyncio.Event()
    unblock = asyncio.Event()
    outcome = batch()
    attempts = []

    async def receiver(request):
        event = json.loads(request.content)
        assert request.headers["x-api-key"] == settings.callback_api_key.get_secret_value()
        assert request.url.host == "platform.example.com"
        assert request.url.path.endswith(f"/{event['batchId']}/jobs/{event['jobId']}/events")
        if event["kind"] == "PROGRESS" and event["batchId"] == outcome["batchId"]:
            attempts.append(bytes(request.content))
            if len(attempts) == 1:
                pending.set()
                await unblock.wait()
                return httpx.Response(503)
        return httpx.Response(204)

    runner = FakeRunner(blocked=True, quality="PARTIAL", rows=[])
    async with session(settings, runner, receiver) as (client, coord, seen):
        assert (await post(client, settings, outcome)).status_code == 202
        await asyncio.wait_for(pending.wait(), timeout=4)
        assert coord.lanes and not runner.release.is_set()
        assert (await post(client, settings, batch(2, count=1), owner=2)).status_code == 202
        await until(lambda: len(runner.calls) == 2)
        runner.release.set()
        await until(lambda: not coord.lanes)
        assert (await job_request(client, settings, outcome, "results")).json()["data"] == []
        unblock.set()
        await until(lambda: not coord.relay.tasks)
        assert len(attempts) >= 2 and attempts[0] == attempts[1]
        events = [json.loads(body) for _, body in seen]
        terminal = next(event for event in events if event["kind"] == "TERMINAL")
        assert terminal["quality"] == "PARTIAL" and terminal["snapshotId"]
        assert terminal["schemaVersion"] == "1.0" and "results" not in terminal
        streams = {}
        for event in events:
            seq = streams.setdefault(event["jobId"], [])
            assert not seq or seq[-1] <= event["sequence"]
            seq.append(event["sequence"])


async def test_prefix_ack_purge_and_restart(settings):
    payload = batch(count=3)
    async with session(settings, FakeRunner(interrupt=True, quality="SUCCESS_WITH_ISSUES")) as (
        client,
        coord,
        _,
    ):
        accepted = await post(client, settings, payload, key="lost-response")
        await until(lambda: not coord.lanes)
        state = (await status(client, settings, payload)).json()["data"]
        assert [row["status"] for row in state["jobs"]] == ["COMPLETED", "INTERRUPTED", "SKIPPED"]
        assert state["jobs"][0]["quality"] == "SUCCESS_WITH_ISSUES"
        for file in settings.metadata_path.parent.glob("metadata.sqlite3*"):
            if file.suffix == ".lock":
                continue
            data = file.read_bytes()
            assert all(
                raw not in data
                for raw in (
                    b"PRIVATE_KEYWORD_FIXTURE",
                    b"PRIVATE_LOCATION_FIXTURE",
                    b"PRIVATE_RESULT_FIXTURE",
                    b"lost-response",
                )
            )
        assert coord.store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert coord.store.db.execute("PRAGMA synchronous").fetchone()[0] == 2
        first = await job_request(client, settings, payload, "ack", "POST", actor="platform")
        again = await job_request(client, settings, payload, "ack", "POST", actor="platform")
        assert first.status_code == 200 and first.json() == again.json()
    runner = FakeRunner()
    async with session(settings, runner) as (client, _, _):
        assert (
            await post(client, settings, payload, key="lost-response")
        ).json() == accepted.json()
        assert not runner.calls
        assert (await job_request(client, settings, payload, "results")).status_code == 410
        assert (await status(client, settings, payload)).json()["data"]["jobs"][0][
            "availability"
        ] == "UNAVAILABLE"
        for _ in range(2):
            assert (
                await job_request(client, settings, payload, "purge", "POST", actor="platform")
            ).json()["data"]["availability"] == "PURGED"
        assert (
            await job_request(client, settings, payload, "ack", "POST", actor="platform")
        ).json() == first.json()
