"""Publication requests and responses. Invitation hashes are never included."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.publication import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    PublicationStatus,
    PublicationVisibility,
)
from app.schemas.post import AuthorPublic

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RESERVED_SLUGS = {"mine"}
InviteRole = Literal["editor", "author", "contributor"]


def _clean_required(value: str, *, max_length: int, label: str) -> str:
    cleaned = " ".join(value.split())
    if cleaned == "":
        raise ValueError(f"{label} cannot be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return cleaned


def _clean_optional(value: str | None, *, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if cleaned == "":
        return None
    if len(cleaned) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return cleaned


def _http_url(value: str | None) -> str | None:
    cleaned = _clean_optional(value, max_length=500, label="Website")
    if cleaned is None:
        return None
    parsed = urlparse(cleaned)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Website must be an absolute http or https URL.")
    return cleaned


def _slug(value: str | None) -> str | None:
    if value is None:
        return None
    slug = value.strip().lower()
    if not _SLUG.fullmatch(slug) or len(slug) > 120 or slug in _RESERVED_SLUGS:
        raise ValueError("Slug must be a lowercase URL path segment.")
    return slug


class BrandingRead(BaseModel):
    """A logo or cover image. Storage keys are not included."""

    media_id: UUID
    url: str | None


class PublicationPublic(BaseModel):
    """Profile visible for an active public publication."""

    id: UUID
    name: str
    slug: str
    description: str | None
    website_url: str | None
    contact_email: str | None
    logo: BrandingRead | None = None
    cover: BrandingRead | None = None
    owner: AuthorPublic
    created_at: datetime


class PublicationPage(BaseModel):
    items: list[PublicationPublic]
    page: int
    page_size: int
    total: int


class PublicationCreate(BaseModel):
    """Fields accepted when a verified user opens a publication."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str | None = None
    description: str | None = None
    website_url: str | None = None
    contact_email: EmailStr | None = None
    visibility: PublicationVisibility = PublicationVisibility.PUBLIC
    logo_media_id: UUID | None = None
    cover_media_id: UUID | None = None
    requires_review: bool = True
    editors_can_invite: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_required(value, max_length=120, label="Name")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        return _slug(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=4000, label="Description")

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        return _http_url(value)

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower()


class PublicationUpdate(BaseModel):
    """Editable publication settings. Ownership is transferred on its own route."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    website_url: str | None = None
    contact_email: EmailStr | None = None
    visibility: PublicationVisibility | None = None
    logo_media_id: UUID | None = None
    cover_media_id: UUID | None = None
    requires_review: bool | None = None
    editors_can_invite: bool | None = None
    status: Literal["active", "suspended"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required(value, max_length=120, label="Name")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        return _slug(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _clean_optional(value, max_length=4000, label="Description")

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        return _http_url(value)

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower()


class PublicationMineItem(BaseModel):
    id: UUID
    name: str
    slug: str
    visibility: PublicationVisibility
    status: PublicationStatus
    role: MembershipRole
    membership_status: MembershipStatus


class PublicationMinePage(BaseModel):
    items: list[PublicationMineItem]
    page: int
    page_size: int
    total: int


class PublicationManage(PublicationPublic):
    """Settings for an active member. Platform role is not included."""

    visibility: PublicationVisibility
    status: PublicationStatus
    requires_review: bool
    editors_can_invite: bool
    caller_role: MembershipRole
    member_count: int


class MemberRead(BaseModel):
    id: UUID
    role: MembershipRole
    status: MembershipStatus
    joined_at: datetime
    user: AuthorPublic


class MemberPage(BaseModel):
    items: list[MemberRead]
    page: int
    page_size: int
    total: int


class MemberRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: InviteRole


class OwnershipTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: InviteRole

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: MembershipRole
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    invited_by: AuthorPublic


class InvitationPage(BaseModel):
    items: list[InvitationRead]
    page: int
    page_size: int
    total: int


class InvitationCreated(BaseModel):
    invitation: InvitationRead
    email_delivery: Literal["sent", "not_configured", "failed"]
    message: str


class InvitationAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)


class PublicationAuditRead(BaseModel):
    id: UUID
    action: str
    previous_value: str | None
    new_value: str | None
    created_at: datetime
    actor: AuthorPublic
    target: AuthorPublic | None = None


class PublicationAuditPage(BaseModel):
    items: list[PublicationAuditRead]
    page: int
    page_size: int
    total: int
