"""Application and database health endpoints."""

from fastapi import APIRouter, Response, status

from app.core.dependencies import SettingsDep
from app.schemas.health import DatabaseHealth, HealthStatus
from app.services.health import database_is_reachable

router = APIRouter()


@router.get(
    "",
    response_model=HealthStatus,
    summary="Application health",
)
def read_health(response: Response, settings: SettingsDep) -> HealthStatus:
    """Report that the API process is running."""

    response.headers["Cache-Control"] = "no-store"
    return HealthStatus(
        status="ok",
        name=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/database",
    response_model=DatabaseHealth,
    summary="Database health",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": DatabaseHealth,
            "description": "PostgreSQL could not be reached.",
        }
    },
)
def read_database_health(response: Response) -> DatabaseHealth:
    """Verify PostgreSQL connectivity without exposing infrastructure details."""

    response.headers["Cache-Control"] = "no-store"
    if database_is_reachable():
        return DatabaseHealth(status="ok", database="connected")

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return DatabaseHealth(status="unavailable", database="disconnected")
