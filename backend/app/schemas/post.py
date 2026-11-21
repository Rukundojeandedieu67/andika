"""Article request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.post import PostStatus
from app.schemas.category import CategoryBrief
from app.schemas.tag import TagBrief

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RESERVED_SLUGS = {"mine", "admin"}


def _clean_required(value: str, *, max_length: int, label: str) -> str:
    cleaned = value.strip()
    if cleaned == "":
        raise ValueError(f"{label} cannot be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return cleaned


def _clean_optional(value: str | None, *, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    if len(cleaned) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return cleaned


def _http_url(value: str | None) -> str | None:
    cleaned = _clean_optional(value, max_length=500, label="Featured image")
    if cleaned is None:
        return None
    parsed = urlparse(cleaned)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Featured image must be an absolute http or https URL.")
    return cleaned


class AuthorPublic(BaseModel):
    """Author fields that are safe to show with a public article."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    full_name: str | None
    avatar_url: str | None
    bio: str | None


class PostCreate(BaseModel):
    """Fields accepted when an author starts a draft."""

    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str | None = None
    excerpt: str | None = None
    content: str = ""
    featured_image: str | None = None
    is_featured: bool = False
    allow_comments: bool = True
    meta_title: str | None = None
    meta_description: str | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] = Field(default_factory=list)

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, value: list[UUID]) -> list[UUID]:
        unique = list(dict.fromkeys(value))
        if len(unique) > 20:
            raise ValueError("An article can have at most 20 tags.")
        return unique

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_required(value, max_length=200, label="Title")

    @field_validator("subtitle")
    @classmethod
    def validate_subtitle(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=300, label="Subtitle")

    @field_validator("excerpt")
    @classmethod
    def validate_excerpt(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=500, label="Excerpt")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if len(value) > 100_000:
            raise ValueError("Content must be at most 100000 characters.")
        return value

    @field_validator("featured_image")
    @classmethod
    def validate_featured_image(cls, value: str | None) -> str | None:
        return _http_url(value)

    @field_validator("meta_title")
    @classmethod
    def validate_meta_title(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=70, label="Meta title")

    @field_validator("meta_description")
    @classmethod
    def validate_meta_description(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=160, label="Meta description")


class PostUpdate(BaseModel):
    """Editable article fields. Identity and lifecycle timestamps are rejected."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    slug: str | None = None
    subtitle: str | None = None
    excerpt: str | None = None
    content: str | None = None
    featured_image: str | None = None
    is_featured: bool | None = None
    allow_comments: bool | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is None:
            return None
        unique = list(dict.fromkeys(value))
        if len(unique) > 20:
            raise ValueError("An article can have at most 20 tags.")
        return unique

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required(value, max_length=200, label="Title")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = value.strip().lower()
        if not _SLUG.fullmatch(slug) or len(slug) > 120 or slug in _RESERVED_SLUGS:
            raise ValueError("Slug must be a lowercase URL path segment.")
        return slug

    @field_validator("subtitle")
    @classmethod
    def validate_subtitle(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=300, label="Subtitle")

    @field_validator("excerpt")
    @classmethod
    def validate_excerpt(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=500, label="Excerpt")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) > 100_000:
            raise ValueError("Content must be at most 100000 characters.")
        return value

    @field_validator("featured_image")
    @classmethod
    def validate_featured_image(cls, value: str | None) -> str | None:
        return _http_url(value)

    @field_validator("meta_title")
    @classmethod
    def validate_meta_title(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=70, label="Meta title")

    @field_validator("meta_description")
    @classmethod
    def validate_meta_description(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=160, label="Meta description")


class PostRead(BaseModel):
    """Article returned to readers and to its editors."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    subtitle: str | None
    excerpt: str | None
    content: str
    featured_image: str | None
    status: PostStatus
    is_featured: bool
    allow_comments: bool
    meta_title: str | None
    meta_description: str | None
    reading_time: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    author: AuthorPublic
    category: CategoryBrief | None = None
    tags: list[TagBrief] = Field(default_factory=list)


class PostPage(BaseModel):
    """One page of articles."""

    items: list[PostRead]
    page: int
    page_size: int
    total: int


class PostListParams(BaseModel):
    """Shared listing filters. Invalid pages are rejected by the route."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    search: str | None = Field(default=None, max_length=200)
    author_id: UUID | None = None
    featured: bool | None = None
    category: str | None = Field(default=None, max_length=120)
    tag: str | None = Field(default=None, max_length=120)
    status: PostStatus | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
