import json
from uuid import uuid4

import httpx
import pytest

from prospector_service.adapters.callbacks import CallbackClient, CallbackPolicy
from prospector_service.schemas import JobEvent, JobStatus, utc_now

from .conftest import JOB_ID


def event():
    return JobEvent(
        eventId=uuid4(),
        jobId=JOB_ID,
        sequence=1,
        status=JobStatus.RUNNING,
        timestamp=utc_now(),
        progress=None,
        results=None,
        error=None,
    )


@pytest.mark.parametrize("outcome", [500, 429, 408, "timeout", "network"])
async def test_retries_preserve_exact_event(settings, outcome):
    bodies = []

    def handle(request):
        bodies.append(request.content)
        if len(bodies) == 1:
            if outcome == "timeout":
                raise httpx.ReadTimeout("safe test timeout")
            if outcome == "network":
                raise httpx.ConnectError("safe test disconnect")
            return httpx.Response(outcome)
        return httpx.Response(200, json={"success": True, "data": {}, "meta": {}})

    client = CallbackClient(settings, transport=httpx.MockTransport(handle))
    original = event()
    try:
        assert await client.send(
            "https://platform.example.com/api/v1/internal/prospecting-jobs/c111111111111111111111111/events",
            original,
        )
    finally:
        await client.close()
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    assert json.loads(bodies[0])["eventId"] == str(original.eventId)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 301, 302, 307])
async def test_permanent_failure_or_redirect_is_not_retried(settings, status):
    seen = []

    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(status, headers={"Location": "https://attacker.example.com/"})

    client = CallbackClient(settings, transport=httpx.MockTransport(handle))
    try:
        assert not await client.send(
            "https://platform.example.com/api/v1/internal/prospecting-jobs/c111111111111111111111111/events",
            event(),
        )
    finally:
        await client.close()
    assert seen == [
        "https://platform.example.com/api/v1/internal/prospecting-jobs/c111111111111111111111111/events"
    ]


async def test_bounded_failure_and_missing_credentials(settings):
    seen = []

    def handle(request):
        seen.append(request.content)
        return httpx.Response(503)

    client = CallbackClient(settings, transport=httpx.MockTransport(handle))
    try:
        assert not await client.send(
            "https://platform.example.com/api/v1/internal/prospecting-jobs/c111111111111111111111111/events",
            event(),
        )
        assert len(seen) == settings.callback_max_attempts
        assert len(set(seen)) == 1
    finally:
        await client.close()
    client = CallbackClient(
        settings.model_copy(update={"callback_api_key": None}),
        transport=httpx.MockTransport(handle),
    )
    try:
        assert not await client.send(
            "https://platform.example.com/api/v1/internal/prospecting-jobs/c111111111111111111111111/events",
            event(),
        )
        assert len(seen) == settings.callback_max_attempts
    finally:
        await client.close()


@pytest.mark.parametrize("suffix", ["?x=1", "#fragment", "/", "%2f", "\\"])
def test_callback_policy_rejects_variants(settings, payload, suffix):
    with pytest.raises(Exception) as error:
        CallbackPolicy(settings).resolve(payload["callbackUrl"] + suffix, payload["jobId"])
    assert error.value.status == 400
