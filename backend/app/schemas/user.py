"""Public user payloads. Password hashes are never included."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_new_password
from app.models.user import UserRole

_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,29}$")


def normalize_username(value: str) -> str:
    username = value.strip()
    if not _USERNAME.fullmatch(username):
        raise ValueError(
            "Username must be 3 to 30 characters, start with a letter, "
            "and use only letters, numbers, and underscores."
        )
    return username


def normalize_optional_text(
    value: str | None, *, max_length: int, label: str
) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    if len(stripped) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    return stripped


def normalize_avatar_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    if len(stripped) > 500:
        raise ValueError("Avatar URL must be at most 500 characters.")
    parsed = urlparse(stripped)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Avatar URL must be an absolute http or https URL.")
    return stripped


class UserPublic(BaseModel):
    """Account fields that are safe to return to a client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    bio: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class UserUpdate(BaseModel):
    """Profile fields a user may change. Privileged fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    username: str | None = None
    full_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_username(value)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, max_length=120, label="Full name")

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, max_length=1000, label="Bio")

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        return normalize_avatar_url(value)


class RegisterAccount(BaseModel):
    """Fields required to open a reader account."""

    model_config = ConfigDict(extra="forbid")

    username: str
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    password_confirm: str = Field(min_length=12, max_length=1024)
    full_name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, max_length=120, label="Full name")

    def validate_password_strength(self) -> None:
        if self.password != self.password_confirm:
            raise ValueError("Password confirmation does not match.")
        validate_new_password(
            self.password, username=self.username, email=str(self.email)
        )
