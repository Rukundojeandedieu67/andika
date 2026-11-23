"""Editorial responses. Reasons stay off the public article schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.post import AuthorPublic, PostRead


class ChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)

    def cleaned_reason(self) -> str:
        cleaned = " ".join(self.reason.split())
        if cleaned == "":
            raise ValueError("Reason cannot be empty.")
        return cleaned


class EditorialEventRead(BaseModel):
    id: UUID
    action: str
    from_status: str | None
    to_status: str
    reason: str | None
    created_at: datetime
    actor: AuthorPublic


class EditorialPostDetail(PostRead):
    events: list[EditorialEventRead] = Field(default_factory=list)
