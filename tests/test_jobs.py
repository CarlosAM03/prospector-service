import asyncio
from collections import Counter
from dataclasses import replace

from .conftest import FakeRunner, batch, post, session, status, until


async def test_25_concurrent_lanes_and_maximum_queue(settings):
    runner = FakeRunner(blocked=True, crash=True)
    fixtures = [
        (batch(number), (number - 1) // 5 + 1, (number - 1) % 5 + 1) for number in range(1, 26)
    ]
    async with session(settings, runner) as (client, coord, _):
        responses = await asyncio.gather(
            *(
                post(client, settings, item, tenant=tenant, owner=owner)
                for item, tenant, owner in fixtures
            )
        )
        assert [response.status_code for response in responses] == [202] * 25
        await until(lambda: len(runner.order) == 25)
        states = Counter(
            {
                row[0]: row[1]
                for row in coord.store.db.execute(
                    "SELECT status, count(*) FROM jobs GROUP BY status"
                )
            }
        )
        assert states == {"RUNNING": 25, "QUEUED": 100}
        assert (await client.get("/health/ready")).status_code == 200
        for tenant, owner in ((6, 1), (1, 6)):
            assert (
                await post(client, settings, batch(50), tenant=tenant, owner=owner)
            ).status_code == 429
        runner.release.set()
        await until(lambda: not coord.lanes, timeout=10)
        for item, tenant, owner in fixtures:
            state = (await status(client, settings, item, tenant=tenant, owner=owner)).json()[
                "data"
            ]
            actual = [i for bid, i in runner.order if bid == item["batchId"]]
            if item == fixtures[0][0]:
                assert actual == [0]
                assert [job["status"] for job in state["jobs"]] == ["INTERRUPTED"] + ["SKIPPED"] * 4
            else:
                assert actual == [0, 1, 2, 3, 4]
                assert all(job["status"] == "COMPLETED" for job in state["jobs"])


async def test_mixed_batch_sizes_replay_race_and_duplicate_id_rollback(settings):
    runner = FakeRunner(blocked=True)
    async with session(settings, runner) as (client, coord, _):
        payloads = [batch(n, count=n) for n in range(1, 6)]
        responses = await asyncio.gather(
            *(post(client, settings, p, owner=i + 1) for i, p in enumerate(payloads)),
            post(client, settings, payloads[0]),
        )
        assert all(res.status_code == 202 for res in responses)
        assert responses[0].json() == responses[-1].json()
        await until(lambda: len(runner.calls) == 5)
        assert coord.store.db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 15
        runner.release.set()
        await until(lambda: not coord.lanes)
        collisions = batch(8, count=2)
        collisions["jobs"][1]["jobId"] = payloads[0]["jobs"][0]["jobId"]
        assert (await post(client, settings, collisions)).status_code == 409
        assert coord.store.db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 15


async def test_unverified_worker_cleanup_reserves_lane(settings):
    async with session(settings, FakeRunner(crash=True, clean=False)) as (client, coord, _):
        payload = batch(count=1)
        assert (await post(client, settings, payload)).status_code == 202
        await until(lambda: not coord.lanes)
        assert (await status(client, settings, payload)).json()["data"]["active"] is True
        assert (await client.get("/health/ready")).status_code == 503
        assert (await post(client, settings, batch(2), owner=2)).status_code == 503
    async with session(settings) as (client, coord, _):
        assert (await client.get("/health/ready")).status_code == 503
        assert (await post(client, settings, payload)).status_code == 202
        assert not coord.lanes


async def test_snapshot_budget_does_not_evict_retained_snapshot(settings):
    configured = settings.model_copy(
        update={"snapshot_budget_bytes": 1024, "max_snapshot_bytes": 1024}
    )
    runner = FakeRunner(rows=[{"name": "x" * 630, "source": "google_maps"}])
    async with session(configured, runner) as (client, coord, _):
        payload = batch(count=2)
        assert (await post(client, configured, payload)).status_code == 202
        await until(lambda: not coord.lanes)
        state = (await status(client, configured, payload)).json()["data"]
        assert [row["availability"] for row in state["jobs"]] == ["AVAILABLE", "UNAVAILABLE"]
        retained = next(iter(coord.snapshots.items.values()))
        assert coord.snapshots.total == len(retained.data)
        coord.snapshots.items[next(iter(coord.snapshots.items))] = replace(retained, deadline=0)
        state = (await status(client, configured, payload)).json()["data"]
        assert state["jobs"][0]["availability"] == "EXPIRED"
        assert coord.snapshots.total == 0


async def test_invalid_result_is_local_to_the_job(settings):
    runner = FakeRunner(rows=[{"name": "fixture", "source": "google_maps"}] * 2)
    async with session(settings, runner) as (client, coord, _):
        payload = batch(count=1, limit=1)
        assert (await post(client, settings, payload)).status_code == 202
        await until(lambda: not coord.lanes)
        job = (await status(client, settings, payload)).json()["data"]["jobs"][0]
        assert job["status"] == "FAILED" and job["errorCode"] == "RESULT_MAPPING_FAILED"
        assert (await client.get("/health/ready")).status_code == 200
        assert (await post(client, settings, batch(2, count=1, limit=2))).status_code == 202
