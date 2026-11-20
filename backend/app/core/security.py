"""Password hashing and JWT utilities for later authentication work."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_PASSWORD_LENGTH = 1024
ACCESS_TOKEN_TYPE = "access"
_RESERVED_CLAIMS = {"sub", "exp", "iat", "nbf", "type"}
_password_hasher = PasswordHash.recommended()


class TokenError(Exception):
    """Base class for access-token failures."""


class InvalidTokenError(TokenError):
    """Raised when an access token is missing, expired, or not authentic."""

    def __init__(self) -> None:
        super().__init__("Access token is invalid or expired.")


class PasswordHashingError(Exception):
    """Raised when a password cannot be hashed."""

    def __init__(self) -> None:
        super().__init__("Password could not be hashed.")


def hash_password(password: str) -> str:
    """Hash a password with Argon2id. The plain password is never stored."""

    if not isinstance(password, str):
        raise TypeError("Password must be a string.")
    if password.strip() == "":
        raise ValueError("Password must not be empty.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password exceeds the maximum length.")
    try:
        return _password_hasher.hash(password)
    except PwdlibError as exc:
        raise PasswordHashingError() from exc


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a password matches an Argon2 hash."""

    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    if password == "" or password_hash == "":
        return False
    try:
        return _password_hasher.verify(password, password_hash)
    except PwdlibError:
        logger.warning("Rejected an unusable password hash")
        return False


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token for the given subject."""

    if not isinstance(subject, str) or subject.strip() == "":
        raise ValueError("Token subject must not be empty.")

    claims = dict(additional_claims or {})
    overlap = _RESERVED_CLAIMS.intersection(claims)
    if overlap:
        names = ", ".join(sorted(overlap))
        raise ValueError(f"Token claims cannot override reserved fields: {names}.")

    settings = get_settings()
    issued_at = datetime.now(UTC)
    lifetime = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        **claims,
        "sub": subject.strip(),
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "type": ACCESS_TOKEN_TYPE,
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    if isinstance(token, bytes):
        return token.decode("ascii")
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate an access token and return its claims."""

    if not isinstance(token, str) or token.strip() == "":
        raise InvalidTokenError()

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    if not isinstance(payload, dict):
        raise InvalidTokenError()
    subject = payload.get("sub")
    if not isinstance(subject, str) or subject.strip() == "":
        raise InvalidTokenError()
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError()
    return payload


def get_token_subject(token: str) -> str:
    """Return the subject claim from a valid access token."""

    subject = decode_access_token(token)["sub"]
    if not isinstance(subject, str):
        raise InvalidTokenError()
    return subject


MIN_PASSWORD_LENGTH = 12
_COMMON_PASSWORDS = {
    "password1234",
    "password12345",
    "changeme1234",
    "qwerty123456",
    "letmein12345",
    "andika123456",
    "admin1234567",
    "welcome12345",
}
_DUMMY_PASSWORD_HASH: str | None = None


def validate_new_password(
    password: str,
    *,
    username: str | None = None,
    email: str | None = None,
) -> None:
    """Reject passwords that are short, common, or derived from the account."""

    if not isinstance(password, str):
        raise ValueError("Password must be a string.")  # noqa: TRY004
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password exceeds the maximum length.")
    if password.strip() != password or password.strip() == "":
        raise ValueError("Password must not begin or end with spaces.")
    if not any(character.isalpha() for character in password):
        raise ValueError("Password must include a letter.")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must include a number.")
    lowered = password.casefold()
    if lowered in _COMMON_PASSWORDS:
        raise ValueError("Password is too common.")
    if username and username.casefold() in lowered:
        raise ValueError("Password must not contain the username.")
    if email:
        local_part = email.split("@", 1)[0].casefold()
        if len(local_part) >= 4 and local_part in lowered:
            raise ValueError("Password must not contain the email address.")


def dummy_password_hash() -> str:
    """Return a stable Argon2 hash used to even out unknown-account login time."""

    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-1")
    return _DUMMY_PASSWORD_HASH


def generate_opaque_token() -> str:
    """Return a cryptographically secure URL-safe token."""

    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    """Hash a high-entropy token with SHA-256. The raw token is never stored."""

    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return digest
