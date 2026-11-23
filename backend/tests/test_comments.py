"""Threaded comments, reports, and moderation tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import get_session_factory
from app.models.user import User, UserRole

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
    assert response.status_code == 201


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
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _reader(client: TestClient, username: str, email: str, *, verified: bool = True) -> str:
    _register(client, username, email)
    if verified:
        _promote(email, UserRole.READER)
    return _login(client, email)


def _author(client: TestClient, username: str, email: str) -> str:
    _register(client, username, email)
    _promote(email, UserRole.AUTHOR)
    return _login(client, email)


def _admin(client: TestClient) -> str:
    _register(client, "Admin", "admin.comments@example.com")
    _promote("admin.comments@example.com", UserRole.ADMIN)
    return _login(client, "admin.comments@example.com")


def _publish(client: TestClient, token: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "A Discussion Article Title",
        "content": "Enough content to publish this article.",
    }
    payload.update(overrides)
    created = client.post("/api/v1/posts", headers=_auth(token), json=payload)
    assert created.status_code == 201, created.text
    published = client.post(
        f"/api/v1/posts/{created.json()['id']}/publish", headers=_auth(token)
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert isinstance(body, dict)
    return body


def _comment(
    client: TestClient, token: str, post_id: object, body: str = "A useful comment."
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/posts/{post_id}/comments",
        headers=_auth(token),
        json={"body": body},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def test_verified_users_comment_and_guests_cannot(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.comments@example.com")
    reader = _reader(client, "Reader", "reader.comments@example.com")
    article = _publish(client, author)
    guest = client.post(
        f"/api/v1/posts/{article['id']}/comments", json={"body": "Hello there"}
    )
    assert guest.status_code == 401

    empty = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "   <p> </p>"},
    )
    assert empty.status_code == 422
    oversized = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "a" * 2001},
    )
    assert oversized.status_code == 422

    created = _comment(client, reader, article["id"], "<b>Hello</b> readers")
    assert created["status"] == "approved"
    assert created["body"] == "Hello readers"
    _comment(client, author, article["id"], "Thanks for reading.")

    listed = client.get(f"/api/v1/posts/{article['id']}/comments")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert "status" not in listed.json()["items"][0]
    assert "reporter" not in listed.json()["items"][0]


def test_unverified_comments_stay_pending(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.pending@example.com")
    reader = _reader(client, "New", "new.pending@example.com", verified=False)
    article = _publish(client, author)
    created = _comment(client, reader, article["id"], "Please review this.")
    assert created["status"] == "pending"
    public = client.get(f"/api/v1/posts/{article['id']}/comments")
    assert public.json()["total"] == 0
    mine = client.get("/api/v1/comments/mine", headers=_auth(reader))
    assert mine.json()["total"] == 1
    assert mine.json()["items"][0]["status"] == "pending"


def test_threads_stop_at_one_reply(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.thread@example.com")
    reader = _reader(client, "Reader", "reader.thread@example.com")
    other = _author(client, "Bea", "bea.thread@example.com")
    article = _publish(client, author)
    second = _publish(client, other, title="Another Published Article")
    root = _comment(client, reader, article["id"], "Root thought")
    reply = client.post(
        f"/api/v1/posts/{article['id']}/comments/{root['id']}/replies",
        headers=_auth(author),
        json={"body": "I agree with this."},
    )
    assert reply.status_code == 201, reply.text
    nested = client.post(
        f"/api/v1/posts/{article['id']}/comments/{reply.json()['id']}/replies",
        headers=_auth(reader),
        json={"body": "And another level."},
    )
    assert nested.status_code == 409
    cross = client.post(
        f"/api/v1/posts/{second['id']}/comments/{root['id']}/replies",
        headers=_auth(reader),
        json={"body": "Wrong article."},
    )
    assert cross.status_code == 404

    hidden = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{root['id']}/status",
        headers=_auth(author),
        json={"status": "hidden"},
    )
    assert hidden.status_code == 200
    blocked = client.post(
        f"/api/v1/posts/{article['id']}/comments/{root['id']}/replies",
        headers=_auth(reader),
        json={"body": "Still there?"},
    )
    assert blocked.status_code == 409
    public = client.get(f"/api/v1/posts/{article['id']}/comments")
    assert public.json()["total"] == 0


def test_owners_edit_and_delete_only_their_comments(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.own@example.com")
    reader = _reader(client, "Reader", "reader.own@example.com")
    other = _reader(client, "Other", "other.own@example.com")
    article = _publish(client, author)
    comment = _comment(client, reader, article["id"], "Original wording")
    edited = client.patch(
        f"/api/v1/comments/{comment['id']}",
        headers=_auth(reader),
        json={"body": "Revised wording"},
    )
    assert edited.status_code == 200
    assert edited.json()["body"] == "Revised wording"
    assert edited.json()["edited_at"] is not None
    foreign = client.patch(
        f"/api/v1/comments/{comment['id']}",
        headers=_auth(other),
        json={"body": "Not mine"},
    )
    assert foreign.status_code == 404
    foreign_delete = client.delete(
        f"/api/v1/comments/{comment['id']}", headers=_auth(other)
    )
    assert foreign_delete.status_code == 404

    reply = client.post(
        f"/api/v1/posts/{article['id']}/comments/{comment['id']}/replies",
        headers=_auth(author),
        json={"body": "A reply that should remain."},
    )
    assert reply.status_code == 201
    removed = client.delete(f"/api/v1/comments/{comment['id']}", headers=_auth(reader))
    assert removed.status_code == 204
    public = client.get(f"/api/v1/posts/{article['id']}/comments")
    assert public.json()["total"] == 1
    assert public.json()["items"][0]["body"] == "This comment was removed."
    assert public.json()["items"][0]["replies"][0]["body"] == "A reply that should remain."
    assert public.json()["items"][0]["author"]["username"] == "Reader"


def test_visibility_follows_article_state(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.visible@example.com")
    reader = _reader(client, "Reader", "reader.visible@example.com")
    admin = _admin(client)
    closed = _publish(client, author, title="Closed Discussion Article", allow_comments=False)
    denied = client.post(
        f"/api/v1/posts/{closed['id']}/comments",
        headers=_auth(reader),
        json={"body": "Can I speak?"},
    )
    assert denied.status_code == 403

    article = _publish(client, author, title="Open Discussion Article")
    _comment(client, reader, article["id"])
    client.post(f"/api/v1/posts/{article['id']}/archive", headers=_auth(author))
    assert client.get(f"/api/v1/posts/{article['id']}/comments").status_code == 404
    archived = client.post(
        f"/api/v1/posts/{article['id']}/comments",
        headers=_auth(reader),
        json={"body": "After archive"},
    )
    assert archived.status_code == 404

    draft = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Draft Discussion Article", "content": "Hidden."},
    )
    assert (
        client.post(
            f"/api/v1/posts/{draft.json()['id']}/comments",
            headers=_auth(reader),
            json={"body": "On a draft"},
        ).status_code
        == 404
    )

    second = _publish(client, author, title="Moderation Visibility Article")
    pending_reader = _reader(
        client, "Pending", "pending.visible@example.com", verified=False
    )
    pending = _comment(client, pending_reader, second["id"], "Waiting for review")
    approved = client.patch(
        f"/api/v1/moderation/comments/{pending['id']}/status",
        headers=_auth(admin),
        json={"status": "approved", "reason": "Fine"},
    )
    assert approved.status_code == 200
    visible = _comment(client, reader, second["id"], "This one is public")
    client.patch(
        f"/api/v1/moderation/comments/{visible['id']}/status",
        headers=_auth(admin),
        json={"status": "rejected"},
    )
    public = client.get(f"/api/v1/posts/{second['id']}/comments")
    bodies = [item["body"] for item in public.json()["items"]]
    assert "Waiting for review" in bodies
    assert "This one is public" not in bodies


def test_author_and_admin_moderation_are_scoped(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.mod@example.com")
    other = _author(client, "Bea", "bea.mod@example.com")
    reader = _reader(client, "Reader", "reader.mod@example.com")
    admin = _admin(client)
    article = _publish(client, author)
    other_article = _publish(client, other, title="Bea Published Article")
    pending_reader = _reader(client, "Wait", "wait.mod@example.com", verified=False)
    pending = _comment(client, pending_reader, article["id"], "Needs a decision")

    reader_try = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{pending['id']}/status",
        headers=_auth(reader),
        json={"status": "approved"},
    )
    assert reader_try.status_code == 403
    foreign = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{pending['id']}/status",
        headers=_auth(other),
        json={"status": "approved"},
    )
    assert foreign.status_code == 403
    reject = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{pending['id']}/status",
        headers=_auth(author),
        json={"status": "rejected"},
    )
    assert reject.status_code == 403
    approved = client.patch(
        f"/api/v1/posts/{article['id']}/moderation/comments/{pending['id']}/status",
        headers=_auth(author),
        json={"status": "approved", "reason": "Welcome"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    queue = client.get(
        f"/api/v1/posts/{article['id']}/moderation/comments?status=approved",
        headers=_auth(author),
    )
    assert queue.json()["total"] == 1
    other_queue = client.get(
        f"/api/v1/posts/{other_article['id']}/moderation/comments",
        headers=_auth(author),
    )
    assert other_queue.status_code == 403
    admin_queue = client.get(
        "/api/v1/moderation/comments?status=approved", headers=_auth(admin)
    )
    assert admin_queue.status_code == 200
    assert admin_queue.json()["total"] >= 1

    logs = client.get("/api/v1/moderation/logs", headers=_auth(admin))
    assert logs.status_code == 200
    entry = logs.json()["items"][0]
    assert entry["previous_status"] == "pending"
    assert entry["new_status"] == "approved"
    assert entry["action"] == "approve"
    assert client.get("/api/v1/moderation/logs", headers=_auth(reader)).status_code == 403
    assert client.patch("/api/v1/moderation/logs", headers=_auth(reader)).status_code == 405


def test_reports_are_unique_and_private(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.report@example.com")
    reader = _reader(client, "Reader", "reader.report@example.com")
    other = _reader(client, "Other", "other.report@example.com")
    admin = _admin(client)
    article = _publish(client, author)
    comment = _comment(client, reader, article["id"], "Check this statement.")
    invalid = client.post(
        f"/api/v1/comments/{comment['id']}/report",
        headers=_auth(other),
        json={"reason": "bored"},
    )
    assert invalid.status_code == 422
    missing = client.post(
        "/api/v1/comments/11111111-1111-1111-1111-111111111111/report",
        headers=_auth(other),
        json={"reason": "spam"},
    )
    assert missing.status_code == 404
    filed = client.post(
        f"/api/v1/comments/{comment['id']}/report",
        headers=_auth(other),
        json={"reason": "spam", "description": "Repeated promotion"},
    )
    assert filed.status_code == 201, filed.text
    assert "email" not in filed.text
    duplicate = client.post(
        f"/api/v1/comments/{comment['id']}/report",
        headers=_auth(other),
        json={"reason": "spam"},
    )
    assert duplicate.status_code == 409
    public = client.get(f"/api/v1/posts/{article['id']}/comments")
    assert public.json()["total"] == 1
    assert public.json()["items"][0]["body"] == "Check this statement."

    reports = client.get("/api/v1/moderation/reports", headers=_auth(admin))
    assert reports.json()["total"] == 1
    resolved = client.patch(
        f"/api/v1/moderation/reports/{filed.json()['id']}",
        headers=_auth(admin),
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    author_reports = client.get(
        f"/api/v1/posts/{article['id']}/moderation/reports", headers=_auth(author)
    )
    assert author_reports.status_code == 200
    assert author_reports.json()["total"] == 1

