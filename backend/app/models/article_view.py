"""Privacy-conscious article read events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.types import UtcDateTime


class ArticleView(Base):
    """One counted read. The visitor is a hash, never a raw address or client id."""

    __tablename__ = "article_views"
    __table_args__ = (
        Index("ix_article_views_post_id_viewed_at", "post_id", "viewed_at"),
        Index(
            "ix_article_views_post_id_visitor_hash_viewed_at",
            "post_id",
            "visitor_hash",
            "viewed_at",
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
    visitor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(40))
    viewed_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
