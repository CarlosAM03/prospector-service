import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft7Validator, FormatChecker

from prospector_service.main import create_app

from .conftest import another, wait_until

ROOT = Path(__file__).absolute().parents[1]
CONTRACT = ROOT / "docs/contracts/prospector-service-api.v1.yaml"
pytestmark = pytest.mark.contract


def nullable_schema(value):
    if isinstance(value, list):
        return [nullable_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    converted = {key: nullable_schema(item) for key, item in value.items() if key != "nullable"}
    return {"anyOf": [converted, {"type": "null"}]} if value.get("nullable") else converted


def validate(value, name):
    document = nullable_schema(yaml.safe_load(CONTRACT.read_text(encoding="utf-8")))
    schema = {"$ref": f"#/components/schemas/{name}", "components": document["components"]}
    Draft7Validator(schema, format_checker=FormatChecker()).validate(value)


def test_authoritative_snapshot_hash_and_endpoints():
    authority = json.loads((CONTRACT.parent / "authority.json").read_text())
    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == authority["sha256"]
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert set(document["paths"]) == {
        "/api/v1/prospecting/jobs",
        "/api/v1/internal/prospecting-jobs/{jobId}/events",
    }


def test_request_response_and_outgoing_events_against_approved_yaml(
    settings, payload, engine, callbacks
):
    validate(payload, "StartJobRequest")
    with TestClient(create_app(settings, engine=engine, callback_transport=callbacks[1])) as client:
        response = client.post(
            "/api/v1/prospecting/jobs", json=payload, headers={"X-API-Key": "test-inbound-secret"}
        )
        validate(response.json(), "AcceptedJobResponse")
        assert response.status_code == 202
        wait_until(lambda: len(callbacks[0]) == 3)
        for _, _, event in callbacks[0]:
            validate(event, "ProspectingJobEvent")
            UUID(event["eventId"])
            assert set(event) == {
                "eventId",
                "jobId",
                "sequence",
                "status",
                "progress",
                "timestamp",
                "results",
                "error",
            }


@pytest.mark.parametrize(
    "case,status", [("invalid", 400), ("auth", 401), ("duplicate", 409), ("unavailable", 503)]
)
def test_error_envelopes_against_yaml(settings, payload, engine, callbacks, case, status):
    if case == "unavailable":
        engine.available = False
    headers = {"X-API-Key": "test-inbound-secret"}
    with TestClient(create_app(settings, engine=engine, callback_transport=callbacks[1])) as client:
        if case == "duplicate":
            assert (
                client.post("/api/v1/prospecting/jobs", json=payload, headers=headers).status_code
                == 202
            )
        if case == "invalid":
            payload["query"]["limit"] = 101
        elif case == "auth":
            headers = {}
        response = client.post("/api/v1/prospecting/jobs", json=payload, headers=headers)
        assert response.status_code == status
        validate(response.json(), "ErrorResponse")


def test_explicit_engine_input_drifts_without_modifying_authority(
    settings, engine, callbacks, payload
):
    # The YAML admits >100 and blank text; the Engine-compatible implementation rejects both.
    body = another(payload, 4)
    body["query"]["limit"] = 101
    validate(body, "StartJobRequest")
    app = create_app(settings, engine=engine, callback_transport=callbacks[1])
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/prospecting/jobs", json=body, headers={"X-API-Key": "test-inbound-secret"}
            ).status_code
            == 400
        )
    body["query"]["limit"] = 1
    body["query"]["keyword"] = ""
    validate(body, "StartJobRequest")
