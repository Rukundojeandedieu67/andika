"""Editorial activity for publication articles."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class EditorialStatus(str, enum.Enum):
    """Review state for a publication article. Independent articles leave this empty."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"


class EditorialEvent(Base):
    """One validated editorial transition. Rows are not updated or deleted."""

    __tablename__ = "editorial_events"
    __table_args__ = (
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('draft', 'submitted', 'in_review', 'changes_requested', 'approved', 'published')",
            name="from_status",
        ),
        CheckConstraint(
            "to_status IN "
            "('draft', 'submitted', 'in_review', 'changes_requested', 'approved', 'published')",
            name="to_status",
        ),
        Index("ix_editorial_events_post_id_created_at", "post_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    post: Mapped[Post] = relationship()
    actor: Mapped[User] = relationship()
