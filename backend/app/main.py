"""ANDIKA FastAPI application."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.dependencies import SettingsDep
from app.database.session import dispose_engine
from app.schemas.common import RootResponse

logger = logging.getLogger("andika")

_HTTP_ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_429_TOO_MANY_REQUESTS: "too_many_requests",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}


def configure_logging() -> None:
    """Configure process logging without printing secrets."""

    settings = get_settings()
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Log startup and release database connections on shutdown."""

    configure_logging()
    settings = get_settings()
    logger.info(
        "Starting %s %s (%s)",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    yield
    dispose_engine()
    logger.info("Application shutdown complete")


def read_root(settings: SettingsDep) -> RootResponse:
    """Identify the API and point clients at documentation and health."""

    return RootResponse(
        name=settings.app_name,
        version=settings.app_version,
        docs="/docs",
        health=f"{settings.api_v1_prefix}/health",
    )


def _public_http_message(exc: StarletteHTTPException) -> str:
    if isinstance(exc.detail, str) and exc.detail.strip():
        return exc.detail
    return "Request failed."


def _validation_details(exc: RequestValidationError) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for error in exc.errors():
        location = error.get("loc", ())
        details.append(
            {
                "loc": [
                    part if isinstance(part, (str, int)) else str(part)
                    for part in location
                ],
                "message": str(error.get("msg", "Invalid value")),
            }
        )
    return details


def register_exception_handlers(app: FastAPI) -> None:
    """Return a stable error envelope and keep internal failures private."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        response = JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": _public_http_message(exc)}},
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request is invalid.",
                },
                "details": _validation_details(exc),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        _exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                }
            },
        )


def create_app() -> FastAPI:
    """Build the FastAPI application from the current settings."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ANDIKA blog publishing platform API.",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    register_exception_handlers(app)
    app.add_api_route(
        "/",
        read_root,
        methods=["GET"],
        response_model=RootResponse,
        tags=["root"],
        summary="API root",
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
