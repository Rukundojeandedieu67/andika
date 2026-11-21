"""Media request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.media import MediaStatus


def _clean(value: str | None, *, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if cleaned == "":
        return None
    if len(cleaned) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return cleaned


class MediaUpdate(BaseModel):
    """Metadata an owner or administrator may change."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    caption: str | None = None
    alt_text: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return _clean(value, max_length=200, label="Title")

    @field_validator("caption")
    @classmethod
    def validate_caption(cls, value: str | None) -> str | None:
        return _clean(value, max_length=500, label="Caption")

    @field_validator("alt_text")
    @classmethod
    def validate_alt_text(cls, value: str | None) -> str | None:
        return _clean(value, max_length=300, label="Alt text")


class MediaVariantRead(BaseModel):
    """One deliverable rendition. Storage keys are not included."""

    model_config = ConfigDict(from_attributes=True)

    kind: str
    url: str
    width: int
    height: int
    mime_type: str
    file_size: int


class MediaRead(BaseModel):
    """Media metadata safe to return to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str
    file_extension: str
    file_size: int
    width: int | None
    height: int | None
    alt_text: str | None
    caption: str | None
    title: str | None
    status: MediaStatus
    created_at: datetime
    updated_at: datetime
    variants: list[MediaVariantRead] = Field(default_factory=list)


class MediaAdminRead(MediaRead):
    """Media row for an administrator, including the owner."""

    owner_id: UUID


class FeaturedImageRead(BaseModel):
    """Featured image details embedded in an article response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alt_text: str | None
    caption: str | None
    title: str | None
    width: int | None
    height: int | None
    mime_type: str
    variants: list[MediaVariantRead] = Field(default_factory=list)


class MediaPage(BaseModel):
    """One page of the caller's media library."""

    items: list[MediaRead]
    page: int
    page_size: int
    total: int


class MediaAdminPage(BaseModel):
    """One page of media for an administrator."""

    items: list[MediaAdminRead]
    page: int
    page_size: int
    total: int
