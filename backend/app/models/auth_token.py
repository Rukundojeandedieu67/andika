"""Single-use password-reset and email-verification tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime
from app.models.user import User


class PasswordResetToken(Base):
    """A hashed, expiring password-reset token."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class EmailVerificationToken(Base):
    """A hashed, expiring email-verification token."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="email_verification_tokens")
