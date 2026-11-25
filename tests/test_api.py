import json

import pytest

from .conftest import BASE, FakeRunner, batch, headers, job_request, post, session, status, until


@pytest.mark.parametrize("count", range(7))
async def test_cardinality_and_atomic_acceptance(settings, count):
    async with session(settings) as (client, coordinator, _):
        response = await post(client, settings, batch(count=count))
        valid = 1 <= count <= 5
        assert response.status_code == (202 if valid else 400)
        assert coordinator.store.db.execute("SELECT count(*) FROM jobs").fetchone()[0] == (
            count if valid else 0
        )
        if valid:
            assert response.json()["data"]["jobIds"] == [
                job["jobId"] for job in batch(count=count)["jobs"]
            ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("limit", 0),
        ("limit", 151),
        ("limit", True),
        ("limit", "1"),
        ("limit", 1.0),
        ("keyword", " "),
        ("location", ""),
        ("source", "unknown"),
    ],
)
async def test_invalid_query_does_not_write(settings, field, value):
    payload = batch()
    payload["jobs"][-1]["query"][field] = value
    async with session(settings) as (client, coordinator, _):
        assert (await post(client, settings, payload)).status_code == 400
        assert not coordinator.store.db.execute("SELECT id FROM batches").fetchall()


async def test_duplicate_invalid_ids_and_retired_route(settings):
    async with session(settings) as (client, coordinator, _):
        payload = batch()
        payload["jobs"][1]["jobId"] = payload["jobs"][0]["jobId"]
        assert (await post(client, settings, payload)).status_code == 400
        payload = batch()
        payload["jobs"][1]["jobId"] = "invalid"
        assert (await post(client, settings, payload)).status_code == 400
        assert (await client.post("/api/v1/prospecting/jobs")).status_code == 404
        assert (
            await client.post("/api/v1/internal/prospecting-batches/id/jobs/id/events")
        ).status_code == 404
        assert not coordinator.store.db.execute("SELECT id FROM jobs").fetchall()


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "wrong"},
        {"aud": "other"},
        {"solutionId": "other"},
        {"method": "GET"},
        {"path": "/wrong"},
        {"query": "different"},
        {"bodySha256": "wrong"},
        {"idempotencyKey": "wrong"},
        {"exp": 1},
        {"iat": True},
        {"tenantId": "bad"},
        {"sub": "bad"},
    ],
)
async def test_assertion_is_bound(settings, override):
    async with session(settings) as (client, _, _):
        assert (await post(client, settings, batch(), overrides=override)).status_code == 401


async def test_missing_wrong_keys_and_permissions(settings):
    payload = batch()
    raw = json.dumps(payload).encode()
    valid = headers(settings, "POST", BASE, "prospecting:batches:create", key="request", body=raw)
    async with session(settings) as (client, _, _):
        for name, value in (("X-API-Key", "wrong"), ("X-Platform-Assertion", "a.b.c")):
            assert (
                await client.post(BASE, content=raw, headers={**valid, name: value})
            ).status_code == 401
        assert (
            await client.post(BASE, content=raw, headers={"Idempotency-Key": "request"})
        ).status_code == 401
        assert (await post(client, settings, payload, actor="platform")).status_code == 403
        assert (
            await post(client, settings, payload, overrides={"scope": "different"})
        ).status_code == 403
        assert (
            await client.post(BASE, content=b"x" * (settings.max_request_bytes + 1))
        ).status_code == 413


async def test_owner_scope_and_technical_delegation(settings):
    async with session(settings) as (client, coord, _):
        payload = batch(count=1, limit=1)
        assert (await post(client, settings, payload)).status_code == 202
        await until(lambda: not coord.lanes)
        own = await job_request(client, settings, payload, "results")
        assert own.status_code == 200
        assert own.headers["Cache-Control"] == "no-store"
        missing = await job_request(client, settings, batch(7, count=1), "results")
        for claims in ({"tenant": 2}, {"owner": 2}, {"owner": 2, "overrides": {"role": "ADMIN"}}):
            other = await job_request(client, settings, payload, "results", **claims)
            assert other.status_code == missing.status_code == 404
            assert other.json()["error"]["code"] == missing.json()["error"]["code"]
        assert (await status(client, settings, payload, actor="platform")).status_code == 403
        assert (
            await job_request(client, settings, payload, "results", actor="platform")
        ).status_code == 403
        assert (
            await job_request(
                client, settings, payload, "results", actor="platform", scope="import"
            )
        ).status_code == 200
        assert (
            await job_request(client, settings, payload, "export?format=csv", actor="platform")
        ).status_code == 403
        assert (
            await job_request(client, settings, payload, "export?format=csv")
        ).status_code == 200
        assert (
            await job_request(client, settings, payload, "export?format=xlsx")
        ).content.startswith(b"PK")
        assert (await status(client, settings, payload)).json()["data"]["jobs"][0]["ackAt"] is None


async def test_replay_and_conflicts_precede_capacity_check(settings):
    runner = FakeRunner(blocked=True)
    payload = batch(count=2)
    async with session(settings, runner) as (client, coord, _):
        first = await post(client, settings, payload, key="retry")
        coord.unsafe = True
        replay = await post(client, settings, payload, key="retry")
        assert replay.status_code == 202 and replay.json() == first.json()
        assert (await post(client, settings, batch(count=3), key="retry")).status_code == 409
        assert (await post(client, settings, batch(2), key="different")).status_code == 503
        coord.unsafe = False
        assert (await post(client, settings, batch(2), key="different")).status_code == 409
        runner.release.set()
