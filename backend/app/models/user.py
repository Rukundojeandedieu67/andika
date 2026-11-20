"""User accounts."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.auth_token import EmailVerificationToken, PasswordResetToken

from app.database.base import Base
from app.database.types import UtcDateTime


class UserRole(str, enum.Enum):
    """Authorization roles. Registration can only create readers."""

    READER = "reader"
    AUTHOR = "author"
    ADMIN = "administrator"


class User(Base):
    """A person who can sign in to ANDIKA."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('reader', 'author', 'administrator')",
            name="role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(30), nullable=False)
    username_key: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(String(1000))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            length=32,
            values_callable=lambda roles: [item.value for item in roles],
        ),
        default=UserRole.READER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    sessions: Mapped[list[AuthSession]] = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    email_verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
