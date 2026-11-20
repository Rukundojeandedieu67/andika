"""Profile reads and updates."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserUpdate
from app.services.exceptions import ConflictError


def update_profile(session: Session, user: User, payload: UserUpdate) -> User:
    """Apply the caller's own profile changes."""

    changes = payload.model_dump(exclude_unset=True)
    users = UserRepository(session)
    if "username" in changes:
        username = changes["username"]
        if not username:
            raise ConflictError("Username cannot be empty.")
        existing = users.get_by_username_key(username)
        if existing is not None and existing.id != user.id:
            raise ConflictError("That username is already in use.")
        user.username = username
        user.username_key = username.casefold()
    if "full_name" in changes:
        user.full_name = changes["full_name"]
    if "bio" in changes:
        user.bio = changes["bio"]
    if "avatar_url" in changes:
        user.avatar_url = changes["avatar_url"]
    user.updated_at = datetime.now(UTC)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That username is already in use.") from exc
    return user
