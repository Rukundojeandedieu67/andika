"""User persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Read and write user rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email.casefold()))

    def get_by_username_key(self, username: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.username_key == username.casefold())
        )

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user
