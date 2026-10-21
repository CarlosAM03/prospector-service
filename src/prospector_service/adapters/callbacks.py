import asyncio
from urllib.parse import urlsplit

import httpx

from ..config import Settings
from ..errors import ServiceError
from ..schemas import JobEvent


class CallbackPolicy:
    def __init__(self, settings: Settings):
        self.origin = (settings.platform_callback_origin or "").rstrip("/")

    def resolve(self, supplied: str, job_id: str) -> str:
        path = f"/api/v1/internal/prospecting-jobs/{job_id}/events"
        expected = self.origin + path
        try:
            parsed = urlsplit(supplied)
            if (
                not self.origin
                or supplied not in {path, expected}
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("callback destination not allowed")
        except ValueError as exc:
            raise ServiceError(
                400, "INVALID_CALLBACK_URL", "Callback must match the configured Platform Job URL"
            ) from exc
        return expected


class CallbackClient:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=settings.callback_timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def send(self, url: str, event: JobEvent) -> bool:
        url = CallbackPolicy(self.settings).resolve(url, event.jobId)
        # Serialize once: every retry preserves UUID, sequence, timestamp and bytes.
        payload = event.model_dump_json().encode("utf-8")
        key = self.settings.callback_api_key
        if key is None or not key.get_secret_value().strip():
            return False
        headers = {"X-API-Key": key.get_secret_value(), "Content-Type": "application/json"}
        for attempt in range(self.settings.callback_max_attempts):
            try:
                response = await self.client.post(url, content=payload, headers=headers)
                if response.status_code == 200:
                    try:
                        return response.json().get("success") is True
                    except (ValueError, AttributeError):
                        return False
                retry = response.status_code in {408, 429} or response.status_code >= 500
                if not retry:
                    return False
            except (httpx.TimeoutException, httpx.NetworkError):
                pass
            if attempt + 1 < self.settings.callback_max_attempts:
                await asyncio.sleep(self.settings.callback_backoff * (2**attempt))
        return False

    async def close(self) -> None:
        await self.client.aclose()
