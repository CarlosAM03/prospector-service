import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from .adapters.callbacks import CallbackClient
from .api import BodyLimitMiddleware, error_response, router
from .config import Settings
from .errors import ServiceError
from .jobs import JobService
from .ports import EnginePort, UnavailableEngine


def create_app(
    settings: Settings | None = None,
    *,
    engine: EnginePort | None = None,
    callback_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    if settings is None:
        try:
            settings = Settings.from_env()
        except ValidationError:
            raise RuntimeError("Invalid Service configuration; check environment") from None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        selected = engine
        if selected is None:
            try:
                from .adapters.engine import EngineAdapter

                selected = EngineAdapter(settings)
            except ImportError:
                selected = UnavailableEngine()
        callback = CallbackClient(settings, transport=callback_transport)
        jobs = JobService(settings, selected, callback)
        application.state.jobs = jobs
        try:
            await jobs.start()
            yield
        finally:
            await jobs.stop()

    application = FastAPI(
        title="Prospector Service",
        version="0.1.0.dev0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = settings
    application.add_middleware(BodyLimitMiddleware, limit=settings.max_request_bytes)
    application.include_router(router)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return error_response(400, "INVALID_REQUEST", "Request does not match the Job contract")

    @application.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return error_response(exc.status, exc.code, exc.message)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(exc.status_code, "HTTP_ERROR", "Request could not be processed")

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logging.getLogger(__name__).error("request_failed")
        return error_response(500, "INTERNAL_ERROR", "Service could not process the request")

    return application


app = create_app()
