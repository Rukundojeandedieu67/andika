"""Aggregate search analytics. Rows are not tied to a user."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.types import UtcDateTime


class SearchEvent(Base):
    """One public search. The text is kept for aggregates and then discarded."""

    __tablename__ = "search_events"
    __table_args__ = (
        Index("ix_search_events_created_at_search_type", "created_at", "search_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    search_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
