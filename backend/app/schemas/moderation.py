"""Moderation request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.comment import CommentStatus
from app.models.comment_report import ReportReason, ReportStatus
from app.schemas.post import AuthorPublic


def _optional_text(value: str | None, *, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if cleaned == "":
        return None
    if len(cleaned) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return cleaned


class ModerationStatusUpdate(BaseModel):
    """A moderation decision for one comment."""

    model_config = ConfigDict(extra="forbid")

    status: CommentStatus
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        return _optional_text(value, max_length=500, label="Reason")


class ModerationComment(BaseModel):
    """Comment details visible to the article author or an administrator."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    parent_id: UUID | None
    author_id: UUID
    body: str
    status: CommentStatus
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    author: AuthorPublic


class ModerationCommentPage(BaseModel):
    """One page of comments in a moderation queue."""

    items: list[ModerationComment]
    page: int
    page_size: int
    total: int


class ReportCreate(BaseModel):
    """A report filed by an authenticated user."""

    model_config = ConfigDict(extra="forbid")

    reason: ReportReason
    description: str | None = None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _optional_text(value, max_length=500, label="Description")


class ReportUpdate(BaseModel):
    """Close a report without changing the comment unless a separate decision does."""

    model_config = ConfigDict(extra="forbid")

    status: ReportStatus

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: ReportStatus) -> ReportStatus:
        if value is ReportStatus.OPEN:
            raise ValueError("Choose resolved or dismissed.")
        return value


class ReportRead(BaseModel):
    """A report for moderators. The reporter's email is not included."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    comment_id: UUID
    reason: ReportReason
    description: str | None
    status: ReportStatus
    created_at: datetime
    reviewed_at: datetime | None
    reporter: AuthorPublic


class ReportPage(BaseModel):
    """One page of comment reports."""

    items: list[ReportRead]
    page: int
    page_size: int
    total: int


class ModerationLogRead(BaseModel):
    """One immutable moderation decision."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    moderator_id: UUID
    comment_id: UUID
    action: str
    previous_status: str
    new_status: str
    reason: str | None
    created_at: datetime


class ModerationLogPage(BaseModel):
    """One page of moderation history."""

    items: list[ModerationLogRead]
    page: int
    page_size: int
    total: int
