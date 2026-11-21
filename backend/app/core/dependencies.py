"""FastAPI dependencies shared by API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, decode_access_token
from app.database.session import get_db
from app.database.types import ensure_utc
from app.models.user import User, UserRole
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository

SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)
_AUTH_HEADER = {"WWW-Authenticate": "Bearer"}
_AUTH_MESSAGE = "Authentication is required."


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: DatabaseSession,
) -> User:
    """Load the active user identified by a verified access token and live session."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_MESSAGE,
            headers=_AUTH_HEADER,
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(str(payload.get("sub")))
        session_id = uuid.UUID(str(payload.get("sid")))
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_MESSAGE,
            headers=_AUTH_HEADER,
        ) from exc

    user = UserRepository(session).get_by_id(user_id)
    auth_session = AuthSessionRepository(session).get_by_id(session_id)
    now = datetime.now(UTC)
    session_is_live = (
        auth_session is not None
        and user is not None
        and auth_session.user_id == user.id
        and auth_session.revoked_at is None
        and ensure_utc(auth_session.expires_at) > now
    )
    if user is None or not user.is_active or not session_is_live:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_MESSAGE,
            headers=_AUTH_HEADER,
        )
    return user


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: DatabaseSession,
) -> User | None:
    """Return the caller when a bearer token is present, otherwise None."""

    if credentials is None:
        return None
    return get_current_user(credentials, session)


def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the authenticated user. Inactive accounts are already rejected."""

    return user


def get_current_verified_user(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Require a verified email address."""

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification is required.",
        )
    return user


def _require_role(user: User, allowed: set[UserRole]) -> User:
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification is required.",
        )
    if user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return user


def get_current_author(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    """Allow verified authors and administrators."""

    return _require_role(user, {UserRole.AUTHOR, UserRole.ADMIN})


def get_current_admin(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    """Allow verified administrators."""

    return _require_role(user, {UserRole.ADMIN})


CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
VerifiedUser = Annotated[User, Depends(get_current_verified_user)]
AuthorUser = Annotated[User, Depends(get_current_author)]
AdminUser = Annotated[User, Depends(get_current_admin)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]

__all__ = [
    "ActiveUser",
    "AdminUser",
    "AuthorUser",
    "CurrentUser",
    "DatabaseSession",
    "OptionalUser",
    "SettingsDep",
    "VerifiedUser",
    "get_current_active_user",
    "get_current_admin",
    "get_current_author",
    "get_current_user",
    "get_current_verified_user",
    "get_db",
    "get_optional_user",
    "get_settings",
]
