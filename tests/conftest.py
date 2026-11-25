import asyncio
import base64
import hashlib
import hmac
import json
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
import pytest

from prospector_service.config import Settings
from prospector_service.main import create_app
from prospector_service.runner import Execution
from prospector_service.schemas import utc_now

BASE = "/api/v1/prospecting/batches"


def cuid(number):
    return f"c{number:024d}"


def batch(number=1, count=5, limit=150):
    return {
        "batchId": cuid(number),
        "jobs": [
            {
                "jobId": cuid(number * 10 + index),
                "query": {
                    "source": "google_maps",
                    "keyword": "PRIVATE_KEYWORD_FIXTURE",
                    "location": "PRIVATE_LOCATION_FIXTURE",
                    "limit": limit,
                },
            }
            for index in range(count)
        ],
    }


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def headers(
    settings,
    method,
    url,
    scope,
    *,
    body=b"",
    tenant=1,
    owner=1,
    key="",
    actor="owner",
    overrides=None,
):
    parsed = urlsplit(url)
    now = int(time.time())
    claims = {
        "iss": settings.assertion_issuer,
        "aud": settings.assertion_audience,
        "iat": now,
        "exp": now + 90,
        "solutionId": settings.solution_id,
        "sub": cuid(owner),
        "tenantId": cuid(tenant),
        "scope": scope,
        "actorType": actor,
        "method": method,
        "path": parsed.path,
        "query": parsed.query,
        "idempotencyKey": key,
        "bodySha256": hashlib.sha256(body).hexdigest(),
    }
    claims.update(overrides or {})
    head = b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = b64(json.dumps(claims).encode())
    sig = hmac.digest(
        settings.assertion_key.get_secret_value().encode(), head + b"." + payload, "sha256"
    )
    result = {
        "X-API-Key": settings.internal_api_key.get_secret_value(),
        "X-Platform-Assertion": (head + b"." + payload + b"." + b64(sig)).decode(),
    }
    if key:
        result.update({"Idempotency-Key": key, "Content-Type": "application/json"})
    return result


async def post(client, settings, payload, *, key=None, **claims):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return await client.post(
        BASE,
        content=raw,
        headers=headers(
            settings,
            "POST",
            BASE,
            "prospecting:batches:create",
            body=raw,
            key=key or payload["batchId"],
            **claims,
        ),
    )


async def job_request(client, settings, payload, suffix, verb="GET", **claims):
    path = f"{BASE}/{payload['batchId']}/jobs/{payload['jobs'][0]['jobId']}/{suffix}"
    scope = suffix.split("?", 1)[0]
    scope = claims.pop("scope", "read" if scope == "results" else scope)
    return await client.request(
        verb,
        path,
        headers=headers(
            settings,
            verb,
            path,
            f"prospecting:results:{scope}",
            **claims,
        ),
    )


async def status(client, settings, payload, **claims):
    path = f"{BASE}/{payload['batchId']}"
    return await client.get(
        path,
        headers=headers(
            settings,
            "GET",
            path,
            "prospecting:batches:read",
            **claims,
        ),
    )


class FakeRunner:
    supported = True

    def __init__(
        self,
        *,
        blocked=False,
        crash=False,
        clean=True,
        interrupt=False,
        quality="SUCCESS",
        rows=None,
    ):
        self.release = asyncio.Event()
        if not blocked:
            self.release.set()
        self.crash = crash
        self.clean = clean
        self.interrupt = interrupt
        self.quality = quality
        self.rows = (
            [{"name": "PRIVATE_RESULT_FIXTURE", "source": "google_maps"}] if rows is None else rows
        )
        self.calls = []
        self.order = []

    async def run(self, batch, notify, stop):
        self.calls.append(batch.batchId)

        def event(kind, index, **fields):
            notify({"type": kind, "index": index, "timestamp": utc_now().isoformat(), **fields})

        entries = []
        for index, _ in enumerate(batch.jobs):
            self.order.append((batch.batchId, index))
            event("running", index)
            event(
                "progress",
                index,
                progress={"kind": "metric_updated", "name": "requested_limit", "value": 150},
            )
            if index == 0 and not self.release.is_set():
                tasks = [asyncio.create_task(item.wait()) for item in (stop, self.release)]
                _, waiting = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in waiting:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            if self.crash and batch.batchId == cuid(1) or stop.is_set():
                return Execution(error="ENGINE_EXIT", clean=self.clean)
            if self.interrupt and index == 1:
                return Execution(
                    {"type": "result", "entries": entries, "interrupted": index},
                    error="ENGINE_INTERRUPTED",
                )
            event("awaiting", index)
            entries.append({"status": "COMPLETED", "quality": self.quality, "rows": self.rows})
        return Execution({"type": "result", "entries": entries, "interrupted": None})


@asynccontextmanager
async def session(settings, runner=None, receiver=None):
    seen = []

    async def handle(request):
        seen.append((str(request.url), bytes(request.content)))
        if receiver is not None:
            return await receiver(request)
        return httpx.Response(204)

    app = create_app(
        settings, runner=runner or FakeRunner(), callback_transport=httpx.MockTransport(handle)
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app.state.coordinator, seen


async def until(predicate, timeout=5):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.002)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        app_env="test",
        internal_api_key="a" * 32,
        assertion_key="b" * 32,
        metadata_key="c" * 32,
        callback_api_key="d" * 32,
        platform_callback_origin="https://platform.example.com",
        callback_backoff=0,
        metadata_path=tmp_path / "metadata.sqlite3",
    )
