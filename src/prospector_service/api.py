import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.security import APIKeyHeader

from .errors import ServiceError
from .schemas import AcceptedJobResponse, ErrorBody, ErrorResponse, StartJobRequest

router = APIRouter()
api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


def error_response(status: int, code: str, message: str):
    from fastapi.responses import JSONResponse

    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(body.model_dump(mode="json"), status_code=status)


def authenticate(request: Request, supplied: str | None = Depends(api_key)) -> None:
    key = request.app.state.settings.internal_api_key
    if not key or not key.get_secret_value().strip():
        raise ServiceError(503, "SERVICE_UNAVAILABLE", "Internal authentication is not configured")
    if supplied is None or not secrets.compare_digest(
        supplied.encode("utf-8"),
        key.get_secret_value().encode("utf-8"),
    ):
        raise ServiceError(401, "UNAUTHORIZED", "Internal API key is missing or invalid")


@router.post(
    "/api/v1/prospecting/jobs",
    status_code=202,
    response_model=AcceptedJobResponse,
    dependencies=[Depends(authenticate)],
    responses={status: {"model": ErrorResponse} for status in (400, 401, 409, 503)},
)
async def accept_job(payload: StartJobRequest, request: Request):
    return AcceptedJobResponse(data=await request.app.state.jobs.accept(payload))


@router.get("/health/live")
async def live():
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request):
    from fastapi.responses import JSONResponse

    checks = request.app.state.jobs.readiness()
    available = all(checks.values())
    return JSONResponse(
        {
            "status": "ready" if available else "not_ready",
            "checks": checks,
            "mode": "single-process/non-durable/initial-integration",
        },
        status_code=200 if available else 503,
    )


class BodyLimitMiddleware:
    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                response = error_response(400, "INVALID_REQUEST", "Request body is too large")
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
