import json
import threading
import time
from copy import deepcopy

import httpx
import pytest
from prospector_engine import CancellationToken

from prospector_service.config import Settings
from prospector_service.errors import EngineCancelled
from prospector_service.schemas import BusinessResult

JOB_ID = "c" + "1" * 24
TENANT_ID = "c" + "2" * 24


@pytest.fixture
def settings():
    return Settings(
        app_env="test",
        internal_api_key="test-inbound-secret",
        callback_api_key="test-outbound-secret",
        platform_callback_origin="https://platform.example.com",
        callback_backoff=0,
        shutdown_grace_seconds=0.1,
    )


@pytest.fixture
def payload():
    return {
        "jobId": JOB_ID,
        "tenantId": TENANT_ID,
        "query": {"keyword": "cafes", "location": "Tijuana", "source": "google_maps", "limit": 2},
        "callbackUrl": f"https://platform.example.com/api/v1/internal/prospecting-jobs/{JOB_ID}/events",
    }


class FakeEngine:
    """Test-only injected port; never selected by production configuration."""

    def __init__(self, *, available=True, blocked=False, failure=None, result=None):
        self.available = available
        self.failure = failure
        self.result = (
            result
            if result is not None
            else (BusinessResult(name="CAFE UNO", source="google_maps"),)
        )
        self.calls = []
        self.threads = []
        self.started = threading.Event()
        self.release = threading.Event()
        if not blocked:
            self.release.set()

    def probe(self):
        return self.available

    def new_token(self):
        return CancellationToken()

    def execute(self, query, token):
        self.calls.append(query)
        self.threads.append(threading.get_ident())
        self.started.set()
        while not self.release.wait(0.01):
            if token.is_cancelled:
                raise EngineCancelled()
        if token.is_cancelled:
            raise EngineCancelled()
        if self.failure:
            raise self.failure
        return self.result


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def callbacks():
    received = []

    def handle(request):
        received.append((str(request.url), dict(request.headers), json.loads(request.content)))
        return httpx.Response(200, json={"success": True, "data": {}, "meta": {}})

    return received, httpx.MockTransport(handle)


def another(payload, ordinal):
    result = deepcopy(payload)
    result["jobId"] = "c" + str(ordinal) * 24
    result["callbackUrl"] = (
        f"https://platform.example.com/api/v1/internal/prospecting-jobs/{result['jobId']}/events"
    )
    return result


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > end:
            raise AssertionError("controlled worker did not complete")
        time.sleep(0.005)
