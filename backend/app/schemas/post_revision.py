"""Article revision responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PostRevisionRead(BaseModel):
    """A previous version of an article's title, excerpt, and content."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    edited_by: UUID
    title: str
    excerpt: str | None
    content: str
    revision_number: int
    created_at: datetime
