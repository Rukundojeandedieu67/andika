"""Environment-backed application settings."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import unquote, urlparse

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app import __version__

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"

DEFAULT_DATABASE_URL = "postgresql+psycopg://andika:andika@127.0.0.1:5432/andika"
DEFAULT_JWT_SECRET = "change-me-in-development-only-not-for-production"
_POSTGRES_SCHEMES = {"postgres", "postgresql", "postgresql+psycopg"}
_SQLITE_SCHEMES = {"sqlite", "sqlite+pysqlite"}
_WEAK_DATABASE_PASSWORDS = {"", "andika", "password", "postgres", "admin", "changeme"}
_PLACEHOLDER_MARKERS = ("change-me", "changeme", "replace-me", "replace_this")
_EXACT_PLACEHOLDER_SECRETS = {
    "secret",
    "password",
    "jwt-secret",
    "change-me",
    "changeme",
    "replace-me",
}


def _parse_cors_origins(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS JSON value must be a list.")
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in stripped.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("CORS_ORIGINS must be a comma-separated string or a list.")


def _is_placeholder_secret(secret: str) -> bool:
    normalized = secret.strip().lower()
    if normalized in _EXACT_PLACEHOLDER_SECRETS:
        return True
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
        cli_parse_args=False,
    )

    app_name: str = "ANDIKA"
    app_version: str = __version__
    api_v1_prefix: str = "/api/v1"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = DEFAULT_DATABASE_URL

    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_expire_days: int = Field(default=7, gt=0, le=30)
    password_reset_token_expire_minutes: int = Field(default=30, gt=0, le=120)
    email_verification_token_expire_hours: int = Field(default=24, gt=0, le=72)
    verification_resend_cooldown_seconds: int = Field(default=60, gt=0, le=3600)
    auth_rate_limit_enabled: bool = True

    public_app_url: str = "http://localhost:5173"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    storage_provider: Literal["local", "s3"] = "local"
    media_storage_dir: Path = Field(default=BACKEND_ROOT / "var" / "media")
    media_max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)
    media_max_pixels: int = Field(default=20_000_000, gt=0, le=80_000_000)
    media_max_dimension: int = Field(default=8000, gt=0, le=12000)
    media_large_edge: int = Field(default=1600, gt=0, le=4000)
    media_medium_edge: int = Field(default=800, gt=0, le=4000)
    media_thumbnail_edge: int = Field(default=320, gt=0, le=2000)
    media_webp_quality: int = Field(default=82, ge=1, le=100)
    media_delivery: Literal["private", "public"] = "private"
    media_signed_url_seconds: int = Field(default=3600, gt=0, le=7 * 24 * 3600)
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""

    comment_max_length: int = Field(default=2000, ge=20, le=10000)
    comment_rate_limit_per_hour: int = Field(default=30, gt=0, le=300)
    report_rate_limit_per_hour: int = Field(default=10, gt=0, le=100)

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        prefix = value.strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or "/"

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        algorithm = value.strip().upper()
        allowed = {"HS256", "HS384", "HS512"}
        if algorithm not in allowed:
            raise ValueError("JWT_ALGORITHM must be HS256, HS384, or HS512.")
        return algorithm

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str, info: ValidationInfo) -> str:
        url = value.strip()
        if any(character.isspace() for character in url):
            raise ValueError("DATABASE_URL must not contain whitespace.")
        scheme, separator, remainder = url.partition("://")
        environment = info.data.get("environment", "development")
        if separator and scheme in _SQLITE_SCHEMES:
            if environment != "test":
                raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")
            if not remainder:
                raise ValueError(
                    "DATABASE_URL must include a SQLite database location."
                )
            return url
        if not separator or scheme not in _POSTGRES_SCHEMES:
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")
        if scheme != "postgresql+psycopg":
            url = f"postgresql+psycopg://{remainder}"
        parsed = urlparse(url)
        database_name = parsed.path.lstrip("/")
        if not parsed.hostname or not database_name:
            raise ValueError("DATABASE_URL must include a host and a database name.")
        return url

    @field_validator("public_app_url")
    @classmethod
    def validate_public_app_url(cls, value: str) -> str:
        candidate = value.strip().rstrip("/")
        parsed = urlparse(candidate)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("PUBLIC_APP_URL must be an absolute http or https URL.")
        return candidate

    @property
    def email_delivery_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from_email.strip())

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        return _parse_cors_origins(value)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        validated: list[str] = []
        for origin in origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS origins must be absolute http or https origins without a path."
                )
            validated.append(origin.rstrip("/"))
        return list(dict.fromkeys(validated))

    @field_validator("storage_provider", "media_delivery", mode="before")
    @classmethod
    def normalize_storage_choice(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("media_storage_dir", mode="before")
    @classmethod
    def resolve_media_storage_dir(cls, value: object) -> Path:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return BACKEND_ROOT / "var" / "media"
        path = value if isinstance(value, Path) else Path(str(value)).expanduser()
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return path

    @field_validator("s3_endpoint_url", "s3_public_base_url")
    @classmethod
    def validate_optional_url(cls, value: str) -> str:
        candidate = value.strip().rstrip("/")
        if candidate == "":
            return ""
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Storage URLs must be absolute http or https URLs.")
        return candidate

    @model_validator(mode="after")
    def validate_production_configuration(self) -> Settings:
        if self.storage_provider == "s3":
            if self.s3_bucket.strip() == "" or self.s3_region.strip() == "":
                raise ValueError("S3 storage requires S3_BUCKET and S3_REGION.")
            if self.s3_access_key_id.strip() == "" or self.s3_secret_access_key.strip() == "":
                raise ValueError(
                    "S3 storage requires S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY."
                )
            if _is_placeholder_secret(self.s3_secret_access_key):
                raise ValueError("S3_SECRET_ACCESS_KEY must not be a placeholder.")
        if self.environment != "production":
            return self

        secret = self.jwt_secret_key.strip()
        if len(secret) < 32 or _is_placeholder_secret(secret):
            raise ValueError(
                "Production requires JWT_SECRET_KEY of at least 32 characters "
                "and it must not be a placeholder."
            )
        if self.debug:
            raise ValueError("DEBUG must be false in production.")
        if not self.cors_origins or any("*" in origin for origin in self.cors_origins):
            raise ValueError(
                "Production CORS origins must be an explicit allow-list without wildcards."
            )
        if self.database_url == DEFAULT_DATABASE_URL:
            raise ValueError(
                "Production DATABASE_URL must not use the development default."
            )

        parsed = urlparse(self.database_url)
        password = unquote(parsed.password) if parsed.password is not None else ""
        if password.strip().lower() in _WEAK_DATABASE_PASSWORDS:
            raise ValueError("Production DATABASE_URL must use a non-default password.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
