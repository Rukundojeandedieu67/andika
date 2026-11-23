"""Notification creation, preferences, authorization, and email delivery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database.session import get_session_factory
from app.models.notification import (
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationType,
)
from app.models.user import User, UserRole
from app.services.email_service import EmailResult, EmailService, EmailStatus
from app.services.notification_service import emit
from app.workers.notification_worker import process_pending

PASSWORD = "Sup3rSecret12"


def _register(client: TestClient, username: str, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "full_name": username,
        },
    )
    assert response.status_code == 201, response.text


def _promote(email: str, role: UserRole, *, verified: bool = True) -> None:
    database = get_session_factory()()
    try:
        user = database.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = role
        user.is_verified = verified
        database.commit()
    finally:
        database.close()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user(client: TestClient, username: str, email: str, role: UserRole) -> str:
    _register(client, username, email)
    _promote(email, role)
    return _login(client, email)


def _publish(client: TestClient, token: str, title: str) -> dict:
    created = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={"title": title, "content": "A public article with enough text."},
    )
    assert created.status_code == 201, created.text
    published = client.post(
        f"/api/v1/posts/{created.json()['id']}/publish",
        headers=_auth(token),
    )
    assert published.status_code == 200, published.text
    return published.json()


def _types(client: TestClient, token: str) -> list[str]:
    response = client.get("/api/v1/notifications", headers=_auth(token))
    assert response.status_code == 200, response.text
    return [item["type"] for item in response.json()["items"]]


def _delivery_rows() -> list[tuple[str, int, str | None]]:
    database = get_session_factory()()
    try:
        rows = database.scalars(select(NotificationDelivery)).all()
        return [
            (
                row.status.value if isinstance(row.status, DeliveryStatus) else str(row.status),
                row.attempts,
                row.last_error,
            )
            for row in rows
        ]
    finally:
        database.close()


def test_comments_replies_and_moderation_notify_the_other_person(client: TestClient) -> None:
    author = _user(client, "NoteAda", "note.ada@example.com", UserRole.AUTHOR)
    reader = _user(client, "NoteBen", "note.ben@example.com", UserRole.READER)
    _register(client, "NoteCara", "note.cara@example.com")
    guest = _login(client, "note.cara@example.com")
    article = _publish(client, author, "Notification Article")
    own = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(author),
        json={"body": "The author left a note."},
    )
    assert own.status_code == 201, own.text
    assert _types(client, author) == []

    reply = client.post(
        f"/api/v1/posts/{article['id']}/comments/{own.json()['id']}/replies",
        headers=_auth(reader),
        json={"body": "A reader replies to the author."},
    )
    assert reply.status_code == 201, reply.text
    listed = client.get("/api/v1/notifications", headers=_auth(author))
    assert listed.json()["items"][0]["type"] == "comment_reply_received"
    assert "email" not in listed.json()["items"][0]["actor"]
    assert listed.json()["items"][0]["message"].startswith("NoteBen")
    assert _types(client, reader) == []

    pending = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(guest),
        json={"body": "This comment is waiting for review."},
    )
    assert pending.status_code == 201, pending.text
    approved = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{pending.json()['id']}/status",
        headers=_auth(author),
        json={"status": "approved"},
    )
    assert approved.status_code == 200, approved.text
    assert "comment_approved" in _types(client, guest)
    hidden = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{reply.json()['id']}/status",
        headers=_auth(author),
        json={"status": "hidden"},
    )
    assert hidden.status_code == 200, hidden.text
    assert "comment_hidden" in _types(client, reader)
    foreign = client.patch(
        f"/api/v1/notifications/{listed.json()['items'][0]['id']}/read",
        headers=_auth(reader),
    )
    assert foreign.status_code == 404
    assert client.delete(
        f"/api/v1/notifications/{listed.json()['items'][0]['id']}",
        headers=_auth(reader),
    ).status_code == 404


def test_publication_events_reach_the_affected_accounts(client: TestClient) -> None:
    owner = _user(client, "PubAda", "pub.ada@example.com", UserRole.AUTHOR)
    editor = _user(client, "PubBen", "pub.ben@example.com", UserRole.AUTHOR)
    writer = _user(client, "PubCara", "pub.cara@example.com", UserRole.AUTHOR)
    created = client.post(
        "/api/v1/publications",
        headers=_auth(owner),
        json={"name": "Notice Review", "slug": "notice-review", "requires_review": True},
    )
    assert created.status_code == 201, created.text
    publication_id = created.json()["id"]
    for email, role in (("pub.ben@example.com", "editor"), ("pub.cara@example.com", "author")):
        invited = client.post(
            f"/api/v1/publications/{publication_id}/invitations",
            headers=_auth(owner),
            json={"email": email, "role": role},
        )
        assert invited.status_code == 201, invited.text
    assert "publication_invitation_received" in _types(client, editor)
    invitation = client.get("/api/v1/notifications", headers=_auth(editor)).json()["items"][0]
    assert "token" not in invitation["message"]
    assert invitation["action_url"] is None
    for email, token in (("pub.ben@example.com", editor), ("pub.cara@example.com", writer)):
        raw = _invitation_token(client, email)
        assert client.post(
            "/api/v1/invitations/accept", headers=_auth(token), json={"token": raw}
        ).status_code == 200
    assert "publication_invitation_accepted" in _types(client, owner)

    members = client.get(
        f"/api/v1/publications/{publication_id}/members", headers=_auth(owner)
    )
    assert members.status_code == 200, members.text
    by_name = {item["user"]["username"]: item for item in members.json()["items"]}
    changed = client.patch(
        f"/api/v1/publications/{publication_id}/members/{by_name['PubCara']['id']}",
        headers=_auth(owner),
        json={"role": "editor"},
    )
    assert changed.status_code == 200, changed.text
    assert "publication_member_role_changed" in _types(client, writer)
    removed = client.post(
        f"/api/v1/publications/{publication_id}/members/{by_name['PubBen']['id']}/remove",
        headers=_auth(owner),
    )
    assert removed.status_code == 200, removed.text
    assert "publication_member_removed" in _types(client, editor)

    draft = client.post(
        "/api/v1/posts",
        headers=_auth(writer),
        json={
            "title": "Submitted Notice",
            "content": "Waiting for an editor.",
            "publication_id": publication_id,
        },
    )
    assert draft.status_code == 201, draft.text
    submitted = client.post(
        f"/api/v1/posts/{draft.json()['id']}/submit", headers=_auth(writer)
    )
    assert submitted.status_code == 200, submitted.text
    assert "article_submitted_for_review" in _types(client, owner)
    assert "article_submitted_for_review" not in _types(client, editor)
    assert "article_submitted_for_review" not in _types(client, writer)


def test_preferences_are_private_and_control_each_channel(client: TestClient) -> None:
    author = _user(client, "PrefAda", "pref.ada@example.com", UserRole.AUTHOR)
    reader = _user(client, "PrefBen", "pref.ben@example.com", UserRole.READER)
    other = _user(client, "PrefCara", "pref.cara@example.com", UserRole.READER)
    defaults = client.get("/api/v1/notifications/preferences", headers=_auth(author))
    assert defaults.status_code == 200
    assert defaults.json()["email_comments"] is True
    assert defaults.json()["in_app_comments"] is True
    article = _publish(client, author, "Preference Article")
    disabled_email = client.patch(
        "/api/v1/notifications/preferences",
        headers=_auth(author),
        json={"email_comments": False},
    )
    assert disabled_email.status_code == 200
    assert client.get(
        "/api/v1/notifications/preferences", headers=_auth(other)
    ).json()["email_comments"] is True
    commented = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "Email is turned off for the author."},
    )
    assert commented.status_code == 201
    assert _types(client, author) == ["comment_received"]
    assert _delivery_rows() == []

    client.patch(
        "/api/v1/notifications/preferences",
        headers=_auth(author),
        json={"in_app_comments": False, "email_comments": True},
    )
    again = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(other),
        json={"body": "Only the email channel remains."},
    )
    assert again.status_code == 201
    assert _types(client, author) == ["comment_received"]
    assert len(_delivery_rows()) == 1


def test_notification_access_read_and_rollback(client: TestClient) -> None:
    author = _user(client, "OwnAda", "own.ada@example.com", UserRole.AUTHOR)
    reader = _user(client, "OwnBen", "own.ben@example.com", UserRole.READER)
    article = _publish(client, author, "Owned Notices")
    assert client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "A comment that creates one notice."},
    ).status_code == 201
    first = client.get("/api/v1/notifications", headers=_auth(author)).json()["items"][0]
    marked = client.patch(
        f"/api/v1/notifications/{first['id']}/read", headers=_auth(author)
    )
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True
    again = client.patch(
        f"/api/v1/notifications/{first['id']}/read", headers=_auth(author)
    )
    assert again.json()["read_at"] == marked.json()["read_at"]
    assert client.get(
        "/api/v1/notifications/unread-count", headers=_auth(author)
    ).json()["unread"] == 0
    assert client.get("/api/v1/notifications", headers=_auth(reader)).json()["total"] == 0
    assert client.delete(
        f"/api/v1/notifications/{first['id']}", headers=_auth(author)
    ).status_code == 204

    database = get_session_factory()()
    try:
        recipient = database.scalar(select(User).where(User.email == "own.ada@example.com"))
        assert recipient is not None
        emit(
            database,
            recipient_id=recipient.id,
            actor=None,
            kind=NotificationType.COMMENT_RECEIVED,
            title="Rolled back",
            message="This must not remain.",
            resource_type="post",
            resource_id=None,
            action_url=None,
            details={"token": "secret", "article": "Owned Notices"},
            idempotency_key="rollback-once",
        )
        emit(
            database,
            recipient_id=recipient.id,
            actor=None,
            kind=NotificationType.COMMENT_RECEIVED,
            title="Rolled back",
            message="This must not remain.",
            resource_type="post",
            resource_id=None,
            action_url=None,
            details=None,
            idempotency_key="rollback-once",
        )
        database.rollback()
    finally:
        database.close()
    check = get_session_factory()()
    try:
        remaining = check.scalar(
            select(func.count(Notification.id)).where(Notification.idempotency_key == "rollback-once")
        )
    finally:
        check.close()
    assert remaining == 0


def test_email_worker_retries_and_does_not_repeat_success(client: TestClient, tmp_path) -> None:
    author = _user(client, "MailAda", "mail.ada@example.com", UserRole.AUTHOR)
    reader = _user(client, "MailBen", "mail.ben@example.com", UserRole.READER)
    other = _user(client, "MailCara", "mail.cara@example.com", UserRole.READER)
    admin = _user(client, "MailAdmin", "mail.admin@example.com", UserRole.ADMIN)
    article = _publish(client, author, "Delivery Article")
    assert client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "Please deliver this comment notice."},
    ).status_code == 201

    flaky = _FlakyMail(get_settings())
    first = process_pending(flaky, batch_size=10, max_attempts=3)
    assert first["claimed"] == 1
    assert first["pending"] == 1
    assert flaky.calls == 1
    _release_pending()
    second = process_pending(flaky, batch_size=10, max_attempts=3)
    assert second["sent"] == 1
    third = process_pending(flaky, batch_size=10, max_attempts=3)
    assert third["claimed"] == 0
    assert flaky.calls == 2

    assert client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(other),
        json={"body": "This delivery is rejected."},
    ).status_code == 201
    rejected = process_pending(_PermanentMail(get_settings()), batch_size=10, max_attempts=5)
    assert rejected["failed"] == 1
    assert _delivery_rows()[-1][0] == "failed"
    forbidden = client.get("/api/v1/notifications/admin/delivery", headers=_auth(reader))
    assert forbidden.status_code == 403
    stats = client.get("/api/v1/notifications/admin/delivery", headers=_auth(admin))
    assert stats.status_code == 200, stats.text
    assert stats.json()["failed"] >= 1
    assert "recipient_email" not in stats.text
    assert "@" not in stats.text

    assert client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "SMTP is not configured for this one."},
    ).status_code == 201
    missing = process_pending(EmailService(get_settings()), batch_size=10)
    assert missing["not_configured"] == 1
    assert _delivery_rows()[-1][0] == "not_configured"

    assert client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(other),
        json={"body": "Keep a development copy only."},
    ).status_code == 201
    development = get_settings().model_copy(update={"environment": "development"})
    captured = EmailService(development)
    captured._outbox_directory = lambda: tmp_path  # type: ignore[method-assign]
    copied = process_pending(captured, batch_size=10)
    assert copied["not_configured"] == 1
    saved = next(iter(tmp_path.glob("*.txt"))).read_text(encoding="utf-8")
    assert "New comment" in saved
    assert "Delivery Article" in saved
    assert "Keep a development copy only." not in saved


def test_worker_batch_and_stale_claim_recovery(client: TestClient) -> None:
    author = _user(client, "BatchAda", "batch.ada@example.com", UserRole.AUTHOR)
    readers = [
        _user(client, f"Batch{name}", f"batch.{name.lower()}@example.com", UserRole.READER)
        for name in ("Ben", "Cara", "Dina")
    ]
    article = _publish(client, author, "Batch Article")
    for reader, name in zip(readers, ("Ben", "Cara", "Dina"), strict=True):
        assert client.post(
            f"/api/v1/posts/{article['id']}/comments",
            headers=_auth(reader),
            json={"body": f"{name} left a separate comment."},
        ).status_code == 201
    mail = client.mailbox  # type: ignore[attr-defined]
    before = len(mail.messages)
    first = process_pending(mail, batch_size=2)
    assert first["sent"] == 2
    second = process_pending(mail, batch_size=2)
    assert second["sent"] == 1
    assert len(mail.messages) == before + 3

    assert client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(readers[0]),
        json={"body": "Recover a claim that the worker dropped."},
    ).status_code == 201
    database = get_session_factory()()
    try:
        pending = database.scalar(
            select(NotificationDelivery).where(NotificationDelivery.status == DeliveryStatus.PENDING)
        )
        assert pending is not None
        pending.status = DeliveryStatus.SENDING
        pending.attempts = 1
        pending.updated_at = datetime.now(UTC) - timedelta(minutes=30)
        database.commit()
    finally:
        database.close()
    recovered = process_pending(mail, batch_size=5)
    assert recovered["recovered"] == 1
    assert recovered["sent"] == 1


def test_notification_routes_are_documented(client: TestClient) -> None:
    author = _user(client, "LimitAda", "limit.ada@example.com", UserRole.AUTHOR)
    current = get_settings()
    client.app.dependency_overrides[get_settings] = lambda: current.model_copy(
        update={"auth_rate_limit_enabled": True, "notification_rate_limit_per_hour": 2}
    )
    assert client.patch(
        "/api/v1/notifications/preferences",
        headers=_auth(author),
        json={"email_account": False},
    ).status_code == 200
    assert client.patch(
        "/api/v1/notifications/preferences",
        headers=_auth(author),
        json={"email_account": True},
    ).status_code == 200
    limited = client.patch(
        "/api/v1/notifications/preferences",
        headers=_auth(author),
        json={"email_account": False},
    )
    assert limited.status_code == 429
    schema = client.get("/api/v1/openapi.json")
    assert "/api/v1/notifications" in schema.text
    assert "/api/v1/notifications/unread-count" in schema.text


def _invitation_token(client: TestClient, email: str) -> str:
    matches = [
        item
        for item in client.mailbox.messages  # type: ignore[attr-defined]
        if item["template"] == "publication_invitation" and item["recipient"] == email
    ]
    assert matches
    return str(matches[-1]["body"].split("#token=", 1)[1].split()[0].strip())


def _release_pending() -> None:
    database = get_session_factory()()
    try:
        for row in database.scalars(
            select(NotificationDelivery).where(NotificationDelivery.status == DeliveryStatus.PENDING)
        ):
            row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        database.commit()
    finally:
        database.close()


class _FlakyMail(EmailService):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.calls = 0

    def send_notification(self, *, recipient: str, subject: str, body: str) -> EmailResult:
        self.calls += 1
        if self.calls == 1:
            return EmailResult(status=EmailStatus.FAILED, template="notification")
        return EmailResult(status=EmailStatus.SENT, template="notification")


class _PermanentMail(EmailService):
    def send_notification(self, *, recipient: str, subject: str, body: str) -> EmailResult:
        return EmailResult(status=EmailStatus.PERMANENT_FAILURE, template="notification")
