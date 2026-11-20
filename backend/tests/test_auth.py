"""Authentication, recovery, and authorization tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_admin, get_current_author
from app.core.security import create_access_token, hash_opaque_token
from app.database.session import get_session_factory
from app.main import app
from app.models.auth_session import AuthSession
from app.models.auth_token import EmailVerificationToken, PasswordResetToken
from app.models.user import User, UserRole
from app.services.email_service import EmailService, get_email_service
from tests.mail import RecordingEmailService

PASSWORD = "Sup3rSecret12"
NEW_PASSWORD = "AnotherSecret34"


def _register(
    client: TestClient,
    *,
    username: str = "Ada",
    email: str = "ada@example.com",
    password: str = PASSWORD,
    extra: dict[str, object] | None = None,
) -> object:
    payload: dict[str, object] = {
        "username": username,
        "email": email,
        "password": password,
        "password_confirm": password,
        "full_name": "Ada Lovelace",
    }
    if extra:
        payload.update(extra)
    return client.post("/api/v1/auth/register", json=payload)


def _login(
    client: TestClient, *, email: str = "ada@example.com", password: str = PASSWORD
) -> object:
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _mailbox(client: TestClient) -> RecordingEmailService:
    mailbox = client.mailbox  # type: ignore[attr-defined]
    assert isinstance(mailbox, RecordingEmailService)
    return mailbox


def _token_from(body: str) -> str:
    return body.split("#token=", 1)[1].split()[0].strip()


def _latest(client: TestClient, template: str) -> dict[str, str]:
    matches = [
        message
        for message in _mailbox(client).messages
        if message["template"] == template
    ]
    assert matches
    return matches[-1]


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_register_creates_reader_without_password_hash(client: TestClient) -> None:
    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "Ada"
    assert body["email"] == "ada@example.com"
    assert body["role"] == "reader"
    assert body["is_verified"] is False
    assert "hashed_password" not in body
    assert "password" not in body
    message = _latest(client, "email_verification")
    assert "#token=" in message["body"]
    assert "?token=" not in message["body"]


def test_register_rejects_admin_role_and_duplicates(client: TestClient) -> None:
    created = _register(client)
    assert created.status_code == 201

    privileged = _register(
        client,
        username="Grace",
        email="grace@example.com",
        extra={"role": "administrator"},
    )
    assert privileged.status_code == 422

    duplicate_email = _register(client, username="Other", email="ADA@example.com")
    assert duplicate_email.status_code == 409
    assert (
        duplicate_email.json()["error"]["message"]
        == "That email address is already in use."
    )

    duplicate_username = _register(client, username="ada", email="other@example.com")
    assert duplicate_username.status_code == 409
    assert (
        duplicate_username.json()["error"]["message"]
        == "That username is already in use."
    )


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        (
            {
                "username": "Ada",
                "email": "not-an-email",
                "password": PASSWORD,
                "password_confirm": PASSWORD,
            },
            422,
        ),
        (
            {
                "username": "Ada",
                "email": "ada@example.com",
                "password": "short1",
                "password_confirm": "short1",
            },
            422,
        ),
        (
            {
                "username": "Ada",
                "email": "ada@example.com",
                "password": PASSWORD,
                "password_confirm": "Sup3rSecret13",
            },
            422,
        ),
    ],
)
def test_register_rejects_invalid_input(
    client: TestClient,
    payload: dict[str, str],
    status_code: int,
) -> None:
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == status_code
    assert PASSWORD not in response.text
    assert "short1" not in response.text


def test_login_unknown_email_and_wrong_password_match(client: TestClient) -> None:
    _register(client)
    unknown = _login(client, email="missing@example.com")
    wrong = _login(client, password="WrongPassword99")

    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert unknown.json()["error"]["message"] == "Invalid email or password."


def test_login_rejects_inactive_account_with_the_same_message(
    client: TestClient,
) -> None:
    _register(client)
    database = get_session_factory()()
    try:
        user = database.query(User).one()
        user.is_active = False
        database.commit()
    finally:
        database.close()

    inactive = _login(client)
    wrong = _login(client, email="missing@example.com", password="WrongPassword99")

    assert inactive.status_code == 401
    assert inactive.json() == wrong.json()


def test_login_refresh_logout_and_protected_profile(client: TestClient) -> None:
    _register(client)
    logged_in = _login(client)
    assert logged_in.status_code == 200
    body = logged_in.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert "hashed_password" not in body["user"]
    first_refresh = body["refresh_token"]

    me = client.get("/api/v1/users/me", headers=_auth(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["last_login_at"] is not None

    anonymous = client.get("/api/v1/users/me")
    assert anonymous.status_code == 401

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    second_refresh = rotated.json()["refresh_token"]
    assert second_refresh != first_refresh

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert reused.status_code == 401
    family_revoked = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second_refresh}
    )
    assert family_revoked.status_code == 401

    database = get_session_factory()()
    try:
        stored = database.query(AuthSession).all()
        assert stored
        assert all(row.token_hash != first_refresh for row in stored)
        assert any(row.token_hash == hash_opaque_token(first_refresh) for row in stored)
    finally:
        database.close()


def test_logout_revokes_the_refresh_session(client: TestClient) -> None:
    _register(client)
    logged_in = _login(client)
    access_token = logged_in.json()["access_token"]
    refresh_token = logged_in.json()["refresh_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers=_auth(access_token),
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 204

    profile = client.get("/api/v1/users/me", headers=_auth(access_token))
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert profile.status_code == 401
    assert refreshed.status_code == 401


def test_expired_access_token_is_rejected(client: TestClient) -> None:
    _register(client)
    logged_in = _login(client)
    expired = create_access_token(
        logged_in.json()["user"]["id"],
        expires_delta=timedelta(seconds=-30),
        additional_claims={"sid": str(uuid.uuid4())},
    )

    response = client.get("/api/v1/users/me", headers=_auth(expired))

    assert response.status_code == 401


def test_profile_update_rejects_role_changes(client: TestClient) -> None:
    _register(client)
    access_token = _login(client).json()["access_token"]
    headers = _auth(access_token)

    forbidden = client.patch(
        "/api/v1/users/me", headers=headers, json={"role": "administrator"}
    )
    assert forbidden.status_code == 422

    updated = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"full_name": "Ada King", "bio": "Mathematician", "username": "AdaKing"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Ada King"
    assert updated.json()["username"] == "AdaKing"
    assert updated.json()["role"] == "reader"


def test_forgot_password_response_is_identical_and_reset_works(
    client: TestClient,
) -> None:
    _register(client)
    known = client.post(
        "/api/v1/auth/forgot-password", json={"email": "ada@example.com"}
    )
    unknown = client.post(
        "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
    )

    assert known.status_code == 200
    assert known.json() == unknown.json()
    message = _latest(client, "password_reset")
    assert "#token=" in message["body"]
    assert "?token=" not in message["body"]
    token = _token_from(message["body"])

    database = get_session_factory()()
    try:
        record = database.query(PasswordResetToken).one()
        assert record.token_hash == hash_opaque_token(token)
        assert record.token_hash != token
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        database.commit()
    finally:
        database.close()

    expired = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert expired.status_code == 400

    client.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    fresh = _token_from(_latest(client, "password_reset")["body"])
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": fresh, "password": NEW_PASSWORD},
    )
    assert reset.status_code == 200
    reused = client.post(
        "/api/v1/auth/reset-password",
        json={"token": fresh, "password": "YetAnotherSecret56"},
    )
    assert reused.status_code == 400

    old_login = _login(client, password=PASSWORD)
    new_login = _login(client, password=NEW_PASSWORD)
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_password_reset_revokes_existing_sessions(client: TestClient) -> None:
    _register(client)
    logged_in = _login(client)
    access_token = logged_in.json()["access_token"]
    refresh_token = logged_in.json()["refresh_token"]
    client.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    token = _token_from(_latest(client, "password_reset")["body"])

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert reset.status_code == 200
    assert (
        client.get("/api/v1/users/me", headers=_auth(access_token)).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        ).status_code
        == 401
    )


def test_email_verification_and_resend_cooldown(client: TestClient) -> None:
    _register(client)
    first = _token_from(_latest(client, "email_verification")["body"])
    resent = client.post(
        "/api/v1/auth/resend-verification", json={"email": "missing@example.com"}
    )
    existing = client.post(
        "/api/v1/auth/resend-verification", json={"email": "ada@example.com"}
    )
    assert resent.json() == existing.json()
    assert (
        len(
            [
                item
                for item in _mailbox(client).messages
                if item["template"] == "email_verification"
            ]
        )
        == 1
    )

    database = get_session_factory()()
    try:
        record = database.query(EmailVerificationToken).one()
        record.created_at = datetime.now(UTC) - timedelta(minutes=5)
        database.commit()
    finally:
        database.close()

    client.post("/api/v1/auth/resend-verification", json={"email": "ada@example.com"})
    second = _token_from(_latest(client, "email_verification")["body"])
    assert second != first
    stale = client.post("/api/v1/auth/verify-email", json={"token": first})
    verified = client.post("/api/v1/auth/verify-email", json={"token": second})
    replay = client.post("/api/v1/auth/verify-email", json={"token": second})

    assert stale.status_code == 400
    assert verified.status_code == 200
    assert verified.json()["is_verified"] is True
    assert replay.status_code == 400


def test_forgot_password_does_not_claim_delivery_without_smtp(
    client: TestClient,
) -> None:
    from app.core.config import get_settings

    _register(client)
    app.dependency_overrides[get_email_service] = lambda: EmailService(get_settings())
    known = client.post(
        "/api/v1/auth/forgot-password", json={"email": "ada@example.com"}
    )
    unknown = client.post(
        "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
    )

    assert known.status_code == 200
    assert known.json() == unknown.json()
    assert "not configured" in known.json()["message"]
    assert "has been sent" not in known.json()["message"]


def test_development_outbox_saves_a_copy_without_claiming_delivery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    from pathlib import Path

    from app.core.config import get_settings
    from app.services.email_service import EmailStatus

    assert isinstance(tmp_path, Path)

    settings = get_settings().model_copy(update={"environment": "development"})
    mail = EmailService(settings)
    monkeypatch.setattr(mail, "_outbox_directory", lambda: tmp_path)

    result = mail.send_password_reset(
        recipient="ada@example.com",
        token="reset-token",
        expires_at=datetime.now(UTC),
    )
    saved = list(tmp_path.glob("*.txt"))

    assert mail.can_deliver is False
    assert result.status is EmailStatus.NOT_CONFIGURED
    assert len(saved) == 1
    contents = saved[0].read_text(encoding="utf-8")
    assert "#token=reset-token" in contents
    assert "?token=" not in contents


def test_role_dependencies_reject_readers_and_allow_admins() -> None:
    reader = User(
        username="Ada",
        username_key="ada",
        email="ada@example.com",
        hashed_password="hashed",
        role=UserRole.READER,
        is_active=True,
        is_verified=True,
    )
    with pytest.raises(HTTPException) as denied:
        get_current_author(reader)
    assert denied.value.status_code == 403

    reader.role = UserRole.AUTHOR
    reader.is_verified = False
    with pytest.raises(HTTPException) as unverified:
        get_current_author(reader)
    assert unverified.value.detail == "Email verification is required."

    reader.role = UserRole.ADMIN
    reader.is_verified = True
    assert get_current_author(reader) is reader
    assert get_current_admin(reader) is reader

    reader.role = UserRole.AUTHOR
    with pytest.raises(HTTPException) as not_admin:
        get_current_admin(reader)
    assert not_admin.value.status_code == 403


def test_login_rate_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import rate_limit
    from app.core.config import get_settings

    settings = get_settings().model_copy(update={"auth_rate_limit_enabled": True})
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(rate_limit._login, "limit", 1)
    rate_limit._login.reset()
    payload = {"email": "ada@example.com", "password": "WrongPassword99"}
    first = client.post("/api/v1/auth/login", json=payload)
    second = client.post("/api/v1/auth/login", json=payload)

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "too_many_requests"
    assert second.headers["retry-after"].isdigit()


def test_openapi_lists_auth_routes(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/auth/register" in paths
    assert "429" in paths["/api/v1/auth/register"]["post"]["responses"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/logout" in paths
    assert "/api/v1/auth/forgot-password" in paths
    assert "/api/v1/auth/reset-password" in paths
    assert "/api/v1/auth/verify-email" in paths
    assert "/api/v1/users/me" in paths
