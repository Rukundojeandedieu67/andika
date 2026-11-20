"""Security utility tests."""

from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    get_token_subject,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_reversible_plaintext() -> None:
    password = "correct horse battery"
    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != password
    assert password not in first_hash
    assert first_hash.startswith("$argon2")
    assert first_hash != second_hash
    assert verify_password(password, first_hash) is True
    assert verify_password("wrong-password", first_hash) is False
    assert verify_password(password, "not-a-hash") is False


def test_password_rejects_empty_and_oversized_values() -> None:
    with pytest.raises(ValueError):
        hash_password("   ")
    with pytest.raises(ValueError):
        hash_password("x" * 1025)


def test_access_token_round_trip() -> None:
    token = create_access_token("author-1", additional_claims={"role": "author"})
    payload = decode_access_token(token)

    assert get_token_subject(token) == "author-1"
    assert payload["role"] == "author"
    assert payload["type"] == "access"
    assert isinstance(token, str)
    assert get_settings().jwt_secret_key not in token


def test_access_token_rejects_invalid_tokens() -> None:
    token = create_access_token("author-1")
    _header, _body, signature = token.split(".")
    replacement = "a" if not signature.endswith("a") else "b"
    tampered = f"{_header}.{_body}.{signature[:-1]}{replacement}"

    expired = create_access_token("author-1", expires_delta=timedelta(seconds=-30))

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)
    with pytest.raises(InvalidTokenError):
        decode_access_token("")
    with pytest.raises(InvalidTokenError):
        decode_access_token(expired)


def test_access_token_rejects_wrong_type_and_algorithm() -> None:
    settings = get_settings()
    refresh_token = jwt.encode(
        {"sub": "author-1", "type": "refresh", "iat": 1, "exp": 4_102_444_800},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    other_algorithm = jwt.encode(
        {"sub": "author-1", "type": "access", "iat": 1, "exp": 4_102_444_800},
        "x" * 64,
        algorithm="HS512",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(refresh_token)
    with pytest.raises(InvalidTokenError):
        decode_access_token(other_algorithm)


def test_token_claims_cannot_override_reserved_fields() -> None:
    with pytest.raises(ValueError):
        create_access_token("author-1", additional_claims={"exp": 1, "sub": "other"})
    with pytest.raises(ValueError):
        create_access_token("   ")
