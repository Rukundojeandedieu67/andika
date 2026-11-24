"""Direct-message request and response models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.post import AuthorPublic


class ConversationOpen(BaseModel):
    """Start or reuse a thread with a public username."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=30)


class MessageCreate(BaseModel):
    """A message body. Addresses and tokens are not accepted fields."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=2000)


class MessageRead(BaseModel):
    """One message visible to a participant."""

    id: UUID
    conversation_id: UUID
    body: str
    created_at: datetime
    sender: AuthorPublic
    mine: bool


class ConversationRead(BaseModel):
    """A thread and the other participant. Email is not included."""

    id: UUID
    other: AuthorPublic
    last_message: str | None
    last_message_at: datetime | None
    updated_at: datetime


class MessagePage(BaseModel):
    """One page of a thread, oldest message first."""

    items: list[MessageRead]
    page: int
    page_size: int
    total: int
