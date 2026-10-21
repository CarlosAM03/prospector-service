from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from prospector_service.config import Settings
from prospector_service.main import create_app
from prospector_service.ports import UnavailableEngine

from .conftest import FakeEngine, another, wait_until

HEADERS = {"X-API-Key": "test-inbound-secret"}


def test_acceptance_is_immediate_and_callbacks_contractual(settings, payload, callbacks):
    engine = FakeEngine(blocked=True)
    received, transport = callbacks
    app = create_app(settings, engine=engine, callback_transport=transport)
    with TestClient(app) as client:
        response = client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS)
        assert response.status_code == 202
        assert response.headers["content-type"] == "application/json"
        assert response.json()["data"]["status"] == "QUEUED"
        assert response.json()["meta"] == {} and response.json()["success"] is True
        assert client.get("/health/live").status_code == 200
        engine.release.set()
        wait_until(lambda: len(received) == 3)
        events = [entry[2] for entry in received]
        assert [event["status"] for event in events] == ["QUEUED", "RUNNING", "COMPLETED"]
        assert [event["sequence"] for event in events] == [1, 2, 3]
        assert len({event["eventId"] for event in events}) == 3
        assert all(event["timestamp"].endswith("Z") for event in events)
        assert all(event["progress"] is None for event in events)
        assert events[0]["results"] is None and events[1]["results"] is None
        assert events[2]["results"][0]["name"] == "CAFE UNO"
        assert all(event["error"] is None for event in events)
        assert received[0][1]["x-api-key"] == "test-outbound-secret"


@pytest.mark.parametrize("key", [None, "", "wrong", "Bearer flutter-jwt"])
def test_authentication_rejects_invalid_key(settings, payload, engine, callbacks, key):
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/prospecting/jobs",
            json=payload,
            headers={} if key is None else {"X-API-Key": key},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert not engine.calls


def test_missing_secrets_fails_closed(payload):
    with TestClient(create_app(Settings(app_env="test"), engine=FakeEngine())) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 503
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("jobId", "invalid"),
        ("tenantId", "not-a-cuid"),
        ("query", None),
        ("query.limit", 101),
        ("query.limit", 0),
        ("query.limit", True),
        ("query.limit", "2"),
        ("query.keyword", ""),
        ("query.location", "  "),
        ("query.source", "other"),
        ("callbackUrl", "https://attacker.example.com/steal"),
        ("callbackUrl", "https://platform.example.com@attacker.example.com/path"),
        ("callbackUrl", "/api/v1/internal/prospecting-jobs/other/events"),
        ("callbackUrl", "//attacker.example.com/x"),
    ],
)
def test_invalid_requests_never_execute_engine(settings, payload, engine, callbacks, field, value):
    body = deepcopy(payload)
    parts = field.split(".")
    if len(parts) == 2:
        body[parts[0]][parts[1]] = value
    else:
        body[field] = value
    with TestClient(create_app(settings, engine=engine, callback_transport=callbacks[1])) as client:
        response = client.post("/api/v1/prospecting/jobs", json=body, headers=HEADERS)
        assert response.status_code == 400
        error = response.json()["error"]
        assert set(error) == {"code", "message", "details", "timestamp"}
        assert "input" not in str(error) and "Traceback" not in str(error)
        assert not engine.calls


def test_request_limits_and_malformed_json(settings, payload, engine, callbacks):
    with TestClient(create_app(settings, engine=engine, callback_transport=callbacks[1])) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", content=b"{", headers=HEADERS).status_code
            == 400
        )
        response = client.post("/api/v1/prospecting/jobs", content=b"x" * 65537, headers=HEADERS)
        assert response.status_code == 400 and not engine.calls


def test_duplicate_and_saturation_do_not_promise_work(settings, payload, callbacks):
    settings = settings.model_copy(update={"queue_capacity": 1})
    engine = FakeEngine(blocked=True)
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 202
        )
        assert engine.started.wait(2)
        second = another(payload, 3)
        assert (
            client.post("/api/v1/prospecting/jobs", json=second, headers=HEADERS).status_code == 202
        )
        assert (
            client.post("/api/v1/prospecting/jobs", json=second, headers=HEADERS).status_code == 409
        )
        third = another(payload, 4)
        assert (
            client.post("/api/v1/prospecting/jobs", json=third, headers=HEADERS).status_code == 503
        )
        assert third["jobId"] not in app.state.jobs.registry
        assert client.get("/health/ready").status_code == 503
        engine.release.set()


@pytest.mark.parametrize("engine", [UnavailableEngine(), FakeEngine(available=False)])
def test_readiness_distinguishes_process_from_engine(settings, engine, callbacks, payload):
    with TestClient(create_app(settings, engine=engine, callback_transport=callbacks[1])) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 503
        )


def test_registry_capacity_and_tenant_binding(settings, payload, engine, callbacks):
    settings = settings.model_copy(update={"max_registered_jobs": 1})
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 202
        )
        wait_until(lambda: len(callbacks[0]) == 3)
        assert (
            client.post(
                "/api/v1/prospecting/jobs", json=another(payload, 3), headers=HEADERS
            ).status_code
            == 503
        )
        job = app.state.jobs.lookup(payload["jobId"], payload["tenantId"])
        assert job is not None
        assert app.state.jobs.lookup(payload["jobId"], "c" + "9" * 24) is None


def test_relative_callback_and_no_unapproved_routes(settings, payload, engine, callbacks):
    payload["callbackUrl"] = f"/api/v1/internal/prospecting-jobs/{payload['jobId']}/events"
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    assert set(app.openapi()["paths"]) == {
        "/health/live",
        "/health/ready",
        "/api/v1/prospecting/jobs",
    }
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 202
        )


def test_secrets_and_untrusted_validation_input_never_logged(settings, payload, callbacks, caplog):
    engine = FakeEngine(failure=RuntimeError("test-outbound-secret /private/path <html>"))
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 202
        )
        wait_until(lambda: len(callbacks[0]) == 3)
    terminal = callbacks[0][-1][2]
    assert terminal["status"] == "FAILED"
    assert terminal["error"]["code"] == "ENGINE_UNEXPECTED_ERROR"
    for text in ("test-outbound-secret", "test-inbound-secret", "/private/path", "<html>"):
        assert text not in str(terminal) and text not in caplog.text
    assert "test-inbound-secret" not in repr(settings)


def test_shutdown_requests_cooperative_cancel(settings, payload, callbacks):
    engine = FakeEngine(blocked=True)
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 202
        )
        assert engine.started.wait(2)
    assert callbacks[0][-1][2]["status"] == "CANCELLED"
    assert app.state.jobs.worker.done()


def test_keyword_is_not_silently_normalized(settings, payload, engine, callbacks):
    payload["query"]["keyword"] = "  cafe  "
    with TestClient(create_app(settings, engine=engine, callback_transport=callbacks[1])) as client:
        assert (
            client.post("/api/v1/prospecting/jobs", json=payload, headers=HEADERS).status_code
            == 202
        )
        wait_until(lambda: bool(engine.calls))
        assert engine.calls[0].keyword == "  cafe  "
