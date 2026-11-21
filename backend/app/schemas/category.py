"""Category request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.taxonomy import normalize_taxonomy_name


class CategoryCreate(BaseModel):
    """Fields an administrator may set when creating a global category."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    parent_id: UUID | None = None
    is_active: bool = True

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


class CategoryUpdate(BaseModel):
    """Editable category fields. Identity timestamps cannot be changed."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None

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


class CategoryStatusUpdate(BaseModel):
    """Activate or deactivate a category."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool


class CategoryBrief(BaseModel):
    """Category fields safe to show on a public article."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None


class CategoryNode(BaseModel):
    """One visible category and its visible children."""

    id: UUID
    name: str
    slug: str
    description: str | None
    children: list[CategoryNode] = Field(default_factory=list)


class CategoryDetail(CategoryBrief):
    """A category with its parent and direct children."""

    is_active: bool
    parent: CategoryBrief | None = None
    children: list[CategoryBrief] = Field(default_factory=list)


class CategoryAdmin(BaseModel):
    """Category row for administration, including inactive categories."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    parent_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


CategoryNode.model_rebuild()


class CategoryPage(BaseModel):
    """One page of categories."""

    items: list[CategoryAdmin]
    page: int
    page_size: int
    total: int
