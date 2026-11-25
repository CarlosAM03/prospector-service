from datetime import timedelta

from prospector_service import metadata
from prospector_service.auth import Actor
from prospector_service.metadata import Metadata
from prospector_service.schemas import BatchRequest, utc_now

from .conftest import batch, cuid, post, session, status


async def test_recover_committed_active_batch_without_dispatch(settings):
    payload = batch(count=2)
    actor = Actor(settings.solution_id, cuid(1), cuid(1))
    with_metadata = Metadata(settings.metadata_path, b"c" * 32)
    try:
        import json

        data = json.dumps(payload, separators=(",", ":")).encode()
        receipt, fresh = with_metadata.admit(
            actor, BatchRequest.model_validate(payload), "request", data, True
        )
        assert fresh
        with_metadata.update(
            actor.solution, payload["jobs"][0]["jobId"], utc_now().isoformat(), status="RUNNING"
        )
    finally:
        with_metadata.close()

    async with session(settings) as (client, coordinator, _):
        replay = await post(client, settings, payload, key="request")
        assert replay.status_code == 202 and replay.json()["data"] == receipt.model_dump(
            mode="json"
        )
        state = (await status(client, settings, payload)).json()["data"]
        assert [item["status"] for item in state["jobs"]] == ["INTERRUPTED", "SKIPPED"]
        assert coordinator.unsafe and not coordinator.runner.calls


async def test_idempotency_window_is_48_hours(settings, monkeypatch):
    base = utc_now()
    async with session(settings) as (client, coordinator, _):
        assert (await post(client, settings, batch(count=1), key="request")).status_code == 202
        assert (await post(client, settings, batch(2), key="request")).status_code == 409
        from .conftest import until

        await until(lambda: not coordinator.lanes)
        monkeypatch.setattr(metadata, "utc_now", lambda: base + timedelta(hours=48, seconds=2))
        assert (await post(client, settings, batch(2), key="request")).status_code == 202
        assert (await post(client, settings, batch(count=1), key="other")).status_code == 409
