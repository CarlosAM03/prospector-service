import logging
import sqlite3
import tempfile
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from .adapters.callbacks import CallbackRelay
from .api import error_response, router
from .config import Settings
from .coordinator import Coordinator
from .errors import ServiceError
from .runner import ProcessRunner


def create_app(
    settings: Settings | None = None,
    *,
    runner=None,
    callback_transport: httpx.AsyncBaseTransport | None = None,
):
    if settings is None:
        try:
            settings = Settings.from_env()
        except (ValueError, OSError):
            raise RuntimeError("Invalid Service configuration") from None

    @asynccontextmanager
    async def lifespan(application):
        selected = runner or ProcessRunner(settings)
        previous_temp = tempfile.tempdir
        if runner is None and selected.supported:
            # openpyxl uses worksheet staging files. Keep them on verified volatile storage.
            tempfile.tempdir = str(settings.worker_temp_dir.resolve())
        relay = CallbackRelay(settings, callback_transport)
        try:
            try:
                coordinator = Coordinator(settings, selected, relay)
            except BaseException:
                await relay.close()
                raise
            application.state.coordinator = coordinator
            try:
                coordinator.start()
                yield
            finally:
                await coordinator.close()
        finally:
            tempfile.tempdir = previous_temp

    application = FastAPI(
        title="Prospector Service",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = settings
    application.router.redirect_slashes = False
    application.include_router(router)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return error_response(400, "INVALID_REQUEST", "Request does not match the batch contract")

    @application.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return error_response(exc.status, exc.code, exc.message)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(exc.status_code, "HTTP_ERROR", "Request could not be processed")

    @application.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error):
        request.app.state.coordinator.unsafe = True
        return error_response(503, "SERVICE_UNAVAILABLE", "Metadata is unavailable")

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logging.getLogger(__name__).error("request_failed")
        return error_response(500, "INTERNAL_ERROR", "Request could not be processed")

    return application
