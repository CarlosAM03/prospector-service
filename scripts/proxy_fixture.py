"""Test-only Platform receiver and offline Engine for the Nginx smoke."""

import asyncio
import os

import uvicorn
from fastapi import Request, Response

from prospector_service.config import Settings
from prospector_service.main import create_app
from prospector_service.runner import Execution
from prospector_service.schemas import utc_now


class OfflineEngine:
    supported = True

    async def run(self, batch, notify, stop):
        entries = []
        for index, _ in enumerate(batch.jobs):
            notify({"type": "running", "index": index, "timestamp": utc_now().isoformat()})
            notify(
                {
                    "type": "progress",
                    "index": index,
                    "timestamp": utc_now().isoformat(),
                    "progress": {"kind": "metric_updated", "name": "requested_limit", "value": 1},
                }
            )
            await asyncio.sleep(0.1)
            notify({"type": "awaiting", "index": index, "timestamp": utc_now().isoformat()})
            entries.append(
                {
                    "status": "COMPLETED",
                    "quality": "SUCCESS",
                    "rows": [
                        {"name": "SYNTHETIC_RESULT_SENTINEL", "source": "google_maps"},
                    ],
                }
            )
        return Execution({"type": "result", "entries": entries, "interrupted": None})


def main():
    settings = Settings.from_env()
    app = create_app(settings, runner=OfflineEngine())
    received = {}

    @app.post("/api/v1/internal/prospecting-batches/{batch_id}/jobs/{job_id}/events")
    async def receive(batch_id: str, job_id: str, request: Request):
        if request.headers.get("X-API-Key") != settings.callback_api_key.get_secret_value():
            return Response(status_code=401)
        event = await request.json()
        assert (event["batchId"], event["jobId"]) == (batch_id, job_id)
        assert "results" not in event
        received[event["eventId"]] = event
        return Response(status_code=204)

    @app.get("/__fixture/events")
    async def events():
        return list(received.values())

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), access_log=False)


if __name__ == "__main__":
    main()
