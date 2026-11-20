"""Authenticated profile endpoints."""

from fastapi import APIRouter, HTTPException

from app.core.dependencies import ActiveUser, DatabaseSession
from app.schemas.user import UserPublic, UserUpdate
from app.services.exceptions import ServiceError
from app.services.user_service import update_profile

router = APIRouter()


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/me", response_model=UserPublic, summary="Current user")
def read_current_user(user: ActiveUser) -> UserPublic:
    """Return the profile for the access token's user."""

    return UserPublic.model_validate(user)


@router.patch("/me", response_model=UserPublic, summary="Update current user")
def update_current_user(
    payload: UserUpdate,
    user: ActiveUser,
    session: DatabaseSession,
) -> UserPublic:
    """Update profile fields. Role, verification, and password cannot be changed here."""

    try:
        updated = update_profile(session, user, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return UserPublic.model_validate(updated)
