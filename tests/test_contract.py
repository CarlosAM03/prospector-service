import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from prospector_service.main import create_app

from .conftest import batch, job_request, post, session, status, until

ROOT = Path(__file__).resolve().parents[1] / "docs" / "contracts"
SPEC = json.loads((ROOT / "batch-api.v1.openapi.json").read_text(encoding="utf-8"))
pytestmark = pytest.mark.contract


def validate(value, name):
    Draft202012Validator(
        {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]},
        format_checker=FormatChecker(),
    ).validate(value)


def test_authoritative_snapshot_and_batch_route_inventory(settings):
    historical = (ROOT / "prospector-service-api.v1.yaml").read_bytes()
    authority = json.loads((ROOT / "authority.json").read_text())
    assert hashlib.sha256(historical).hexdigest() == authority["sha256"]
    app = create_app(settings)
    assert app.version == SPEC["info"]["version"] == "1.0.0"
    assert app.openapi()["paths"].keys() == SPEC["paths"].keys()
    assert "/api/v1/prospecting/jobs" not in SPEC["paths"]
    assert SPEC["webhooks"]["PlatformJobEvent"]["post"]["x-path"] not in SPEC["paths"]


async def test_http_and_outbound_event_conform_to_v1_document(settings):
    async with session(settings) as (client, coord, events):
        request = batch(count=2)
        validate(request, "BatchRequest")
        validate((await post(client, settings, request)).json(), "Receipt")
        await until(lambda: not coord.lanes and not coord.relay.tasks)
        validate((await status(client, settings, request)).json(), "BatchStatus")
        validate((await job_request(client, settings, request, "results")).json(), "Results")
        validate((await job_request(client, settings, request, "ack", "POST")).json(), "Ack")
        validate((await job_request(client, settings, request, "purge", "POST")).json(), "Purge")
        validate((await job_request(client, settings, request, "results")).json(), "Error")
        assert events
        for _, data in events:
            validate(json.loads(data), "CallbackEvent")
