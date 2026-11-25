import json

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .auth import KEY, authorize, one_header, unique_object
from .coordinator import snapshot_response
from .errors import ServiceError
from .schemas import BatchRequest, Cuid, ErrorBody, ErrorResponse

router = APIRouter()
BASE = "/api/v1/prospecting/batches"
JOB = BASE + "/{batchId}/jobs/{jobId}"
SECURITY = {"security": [{"ServiceApiKey": [], "PlatformAssertion": []}]}
CACHE = {"Cache-Control": "no-store"}


def error_response(status, code, message):
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=CACHE)


def success(data, status=200):
    return JSONResponse(
        {"success": True, "data": data, "meta": {}}, status_code=status, headers=CACHE
    )


async def read_body(request):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > request.app.state.settings.max_request_bytes:
            raise ServiceError(413, "BODY_TOO_LARGE", "Request body exceeds the configured limit")
        data.extend(chunk)
    return bytes(data)


async def identify(request, scope):
    body = await read_body(request)
    actor = authorize(request, scope, body)
    if body:
        raise ServiceError(400, "INVALID_REQUEST", "This operation requires an empty body")
    return actor


@router.post(BASE, status_code=202, openapi_extra=SECURITY)
async def accept_batch(request: Request):
    body = await read_body(request)
    try:
        key = one_header(request, "Idempotency-Key")
        if not KEY.fullmatch(key):
            raise ValueError("invalid idempotency key")
    except ValueError as exc:
        raise ServiceError(400, "INVALID_REQUEST", "Valid Idempotency-Key is required") from exc
    actor = authorize(request, "prospecting:batches:create", body, key)
    try:
        if (
            one_header(request, "Content-Type").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise ValueError("invalid media type")
        batch = BatchRequest.model_validate(
            json.loads(body.decode(), object_pairs_hook=unique_object)
        )
    except (ValueError, ValidationError, RecursionError) as exc:
        raise ServiceError(
            400, "INVALID_REQUEST", "Request does not match the batch contract"
        ) from exc
    receipt = request.app.state.coordinator.accept(actor, batch, key, body)
    return success(receipt.model_dump(mode="json"), 202)


@router.get(BASE + "/{batchId}", openapi_extra=SECURITY)
async def batch_status(batchId: Cuid, request: Request):
    actor = await identify(request, "prospecting:batches:read")
    return success(request.app.state.coordinator.status(actor, batchId))


@router.get(JOB + "/results", openapi_extra=SECURITY)
async def results(batchId: Cuid, jobId: Cuid, request: Request):
    actor = await identify(request, ("prospecting:results:read", "prospecting:results:import"))
    snapshot = request.app.state.coordinator.get_snapshot(actor, batchId, jobId)
    return Response(snapshot_response(snapshot), media_type="application/json", headers=CACHE)


@router.get(JOB + "/export", openapi_extra=SECURITY)
async def export(
    batchId: Cuid, jobId: Cuid, request: Request, format: str = Query(pattern="^(csv|xlsx)$")
):
    actor = await identify(request, "prospecting:results:export")
    if request.query_params.getlist("format") != [format] or len(request.query_params) != 1:
        raise ServiceError(400, "INVALID_REQUEST", "Provide one export format")
    artifact = await request.app.state.coordinator.export(actor, batchId, jobId, format)
    return Response(
        artifact.content,
        media_type=artifact.content_type,
        headers={
            **CACHE,
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
        },
    )


@router.post(JOB + "/ack", openapi_extra=SECURITY)
async def ack(batchId: Cuid, jobId: Cuid, request: Request):
    actor = await identify(request, "prospecting:results:ack")
    return success(request.app.state.coordinator.acknowledge(actor, batchId, jobId))


@router.post(JOB + "/purge", openapi_extra=SECURITY)
async def purge(batchId: Cuid, jobId: Cuid, request: Request):
    actor = await identify(request, "prospecting:results:purge")
    return success(request.app.state.coordinator.purge(actor, batchId, jobId))


@router.get("/health/live")
async def live():
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request):
    coordinator = request.app.state.coordinator
    available = coordinator.ready
    return JSONResponse(
        {
            "status": "ready" if available else "not_ready",
            "checks": {
                "execution_cleanup": not coordinator.unsafe,
                "credentials": bool(coordinator.settings.credentials_configured),
                "runtime_supported": coordinator.runner.supported,
            },
        },
        status_code=200 if available else 503,
    )
