"""Comment request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.models.comment import CommentStatus
from app.schemas.post import AuthorPublic
from app.services.comment_text import normalize_comment_body


class CommentCreate(BaseModel):
    """A new root comment. Replies use the reply route."""

    model_config = ConfigDict(extra="forbid")

    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return normalize_comment_body(value, max_length=get_settings().comment_max_length)


class CommentUpdate(BaseModel):
    """A replacement body for a comment the caller owns."""

    model_config = ConfigDict(extra="forbid")

    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return normalize_comment_body(value, max_length=get_settings().comment_max_length)


class CommentRead(BaseModel):
    """A public comment. Moderation state and deleted bodies are not included."""

    id: UUID
    body: str
    created_at: datetime
    edited_at: datetime | None
    author: AuthorPublic
    replies: list[CommentRead] = Field(default_factory=list)


class CommentOwned(BaseModel):
    """A comment returned to its author, including its moderation state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    parent_id: UUID | None
    body: str
    status: CommentStatus
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None
    author: AuthorPublic


class CommentPage(BaseModel):
    """One page of discussion threads."""

    items: list[CommentRead]
    page: int
    page_size: int
    total: int


class CommentOwnedPage(BaseModel):
    """One page of the caller's comments."""

    items: list[CommentOwned]
    page: int
    page_size: int
    total: int


CommentRead.model_rebuild()
