"""Stored copies of an article before a content change."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class PostRevision(Base):
    """The article content that was replaced by an edit."""

    __tablename__ = "post_revisions"
    __table_args__ = (UniqueConstraint("post_id", "revision_number"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edited_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    post: Mapped[Post] = relationship(back_populates="revisions")
    editor: Mapped[User] = relationship("User")
