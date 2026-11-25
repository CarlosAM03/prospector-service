import asyncio
import json
import logging
import ssl
from collections import deque
from uuid import uuid4

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)


class CallbackRelay:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=settings.callback_timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            limits=httpx.Limits(max_connections=32),
            verify=(
                ssl.create_default_context(cafile=str(settings.platform_callback_ca_file))
                if settings.platform_callback_ca_file
                else True
            ),
        )
        self.pending = {}
        self.tasks = set()
        self.requests = asyncio.Semaphore(32)
        self.missed = 0

    def offer(self, row, kind, *, progress=None, snapshot=None, timestamp=None):
        if not self.settings.credentials_configured:
            return
        event = {
            "schemaVersion": "1.0",
            "eventId": str(uuid4()),
            "batchId": row["batch_id"],
            "jobId": row["id"],
            "queryIndex": row["position"],
            "sequence": row["sequence"],
            "timestamp": timestamp or row["updated_at"],
            "kind": kind,
            "status": row["status"],
        }
        if progress:
            event["progress"] = progress
        if row["quality"]:
            event["quality"] = row["quality"]
        if row["availability"]:
            event["availability"] = row["availability"]
        if row["error"]:
            event["error"] = {"code": row["error"], "message": "Execution or result unavailable"}
        if snapshot:
            event.update(snapshotId=snapshot.id, expiresAt=snapshot.expires_at.isoformat())
        key = (row["batch_id"], row["id"])
        pending = self.pending.get(key)
        if pending is None:
            if len(self.pending) >= self.settings.max_pending_callback_jobs:
                self.missed += 1
                return
            pending = self.pending[key] = deque()
            task = asyncio.create_task(self._dispatch(key, pending))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        if pending and pending[-1][0] == "PROGRESS":
            pending.pop()
        pending.append((kind, json.dumps(event, separators=(",", ":")).encode()))

    async def _dispatch(self, key, pending):
        try:
            while pending:
                _, payload = pending.popleft()
                if not await self._send(key, payload):
                    self.missed += 1
                    logger.warning("callback_delivery_failed")
        finally:
            del self.pending[key]

    async def _send(self, key, payload):
        batch_id, job_id = key
        base = self.settings.platform_callback_origin.rstrip("/")
        url = f"{base}/api/v1/internal/prospecting-batches/{batch_id}/jobs/{job_id}/events"
        headers = {
            "X-API-Key": self.settings.callback_api_key.get_secret_value(),
            "Content-Type": "application/json",
        }
        for attempt in range(self.settings.callback_max_attempts):
            try:
                async with self.requests, asyncio.timeout(self.settings.callback_timeout):
                    async with self.client.stream(
                        "POST", url, content=payload, headers=headers
                    ) as res:
                        status = res.status_code
                        if 200 <= status < 300:
                            return True
                        if status not in {408, 429} and status < 500:
                            return False
            except (httpx.TransportError, TimeoutError):
                pass
            if attempt + 1 < self.settings.callback_max_attempts:
                await asyncio.sleep(self.settings.callback_backoff * 2**attempt)
        return False

    async def close(self):
        if self.tasks:
            _, pending = await asyncio.wait(self.tasks, timeout=3)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        await self.client.aclose()
