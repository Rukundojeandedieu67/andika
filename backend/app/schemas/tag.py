"""Tag request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.taxonomy import normalize_taxonomy_name


class TagCreate(BaseModel):
    """Fields accepted when an author creates a reusable tag."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_taxonomy_name(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if cleaned == "":
            return None
        if len(cleaned) > 500:
            raise ValueError("Description must be at most 500 characters.")
        return cleaned


class TagUpdate(BaseModel):
    """Administrator edits. Omitted fields stay unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_taxonomy_name(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if cleaned == "":
            return None
        if len(cleaned) > 500:
            raise ValueError("Description must be at most 500 characters.")
        return cleaned


class TagBrief(BaseModel):
    """Tag fields safe to show on a public article."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None


class TagAdmin(TagBrief):
    """Tag row including tags that are not yet used publicly."""

    created_at: datetime
    updated_at: datetime


class TagPage(BaseModel):
    """One page of tags."""

    items: list[TagBrief]
    page: int
    page_size: int
    total: int


class TagAdminPage(BaseModel):
    """One page of tags for an administrator."""

    items: list[TagAdmin]
    page: int
    page_size: int
    total: int
