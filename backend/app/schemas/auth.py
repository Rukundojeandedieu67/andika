"""Authentication request bodies."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.user import RegisterAccount


class RegisterRequest(RegisterAccount):
    """Registration payload. Role and privilege fields are not accepted."""

    @model_validator(mode="after")
    def check_password(self) -> RegisterRequest:
        self.validate_password_strength()
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshRequest(BaseModel):
    """Optional body for API clients. Browsers can omit this and use the cookie."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = Field(default=None, min_length=20, max_length=200)


class LogoutRequest(RefreshRequest):
    """Refresh token to revoke, either in this body or in the auth cookie."""


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=1024)


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()
