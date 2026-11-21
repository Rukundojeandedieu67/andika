"""Articles and previous public slugs."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime
from app.models.tag import post_tags

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.media import Media
    from app.models.post_revision import PostRevision
    from app.models.tag import Tag
    from app.models.user import User


class PostStatus(str, enum.Enum):
    """Article lifecycle. Public reads only return published articles."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Post(Base):
    """An article written by one user."""

    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="status",
        ),
        Index("ix_posts_status_published_at", "status", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False, index=True
    )
    subtitle: Mapped[str | None] = mapped_column(String(300))
    excerpt: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    featured_image: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            name="post_status",
            native_enum=False,
            length=32,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=PostStatus.DRAFT,
        nullable=False,
        index=True,
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_comments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta_title: Mapped[str | None] = mapped_column(String(70))
    meta_description: Mapped[str | None] = mapped_column(String(160))
    reading_time: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        index=True,
    )
    featured_image_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media.id", ondelete="SET NULL"),
        index=True,
    )

    author: Mapped[User] = relationship("User")
    category: Mapped[Category | None] = relationship()
    featured_media: Mapped[Media | None] = relationship()
    tags: Mapped[list[Tag]] = relationship(secondary=post_tags, back_populates="posts")
    revisions: Mapped[list[PostRevision]] = relationship(
        "PostRevision",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostRevision.revision_number",
    )
    redirects: Mapped[list[PostRedirect]] = relationship(
        "PostRedirect",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    @property
    def featured_image_media(self) -> Media | None:
        """Ready image metadata for responses. Deleted and failed images are omitted."""

        media = self.featured_media
        if media is None or media.deleted_at is not None:
            return None
        status = media.status.value if hasattr(media.status, "value") else str(media.status)
        if status != "ready":
            return None
        return media


class PostRedirect(Base):
    """A former slug that points at the article's current slug."""

    __tablename__ = "post_redirects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    post: Mapped[Post] = relationship(back_populates="redirects")
