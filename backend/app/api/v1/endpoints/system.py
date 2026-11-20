"""Non-sensitive application metadata."""

from fastapi import APIRouter, Response

from app.core.dependencies import SettingsDep
from app.schemas.system import SystemInfo

router = APIRouter()


@router.get("", response_model=SystemInfo, summary="System information")
def read_system(response: Response, settings: SettingsDep) -> SystemInfo:
    """Return public application metadata."""

    response.headers["Cache-Control"] = "no-store"
    return SystemInfo(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        api_prefix=settings.api_v1_prefix,
    )
