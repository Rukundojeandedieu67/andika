"""Threaded comments on published articles."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime
from app.models.post import Post
from app.models.user import User


class CommentStatus(str, enum.Enum):
    """Moderation state. Only approved comments are public."""

    PENDING = "pending"
    APPROVED = "approved"
    HIDDEN = "hidden"
    REJECTED = "rejected"


class Comment(Base):
    """A root comment or a single-level reply. Replies cannot contain replies."""

    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'hidden', 'rejected')",
            name="status",
        ),
        Index("ix_comments_post_id_created_at", "post_id", "created_at"),
        Index(
            "ix_comments_approved_created_at",
            "status",
            "created_at",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
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
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("comments.id", ondelete="RESTRICT"),
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CommentStatus] = mapped_column(
        Enum(
            CommentStatus,
            name="comment_status",
            native_enum=False,
            length=16,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)

    post: Mapped[Post] = relationship()
    author: Mapped[User] = relationship(foreign_keys=[author_id])
    parent: Mapped[Comment | None] = relationship(
        remote_side="Comment.id",
        back_populates="replies",
    )
    replies: Mapped[list[Comment]] = relationship(back_populates="parent")
