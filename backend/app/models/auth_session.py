"""Refresh-token sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime
from app.models.user import User


class AuthSession(Base):
    """One refresh-token generation inside a rotation family.

    Only the SHA-256 hash of the refresh token is stored.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    replaced_by_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="sessions")
