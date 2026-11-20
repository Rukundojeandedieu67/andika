"""Article publishing, permissions, and revision tests."""

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
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _author(
    client: TestClient, username: str = "Ada", email: str = "ada.posts@example.com"
) -> str:
    _register(client, username, email)
    _promote(email, UserRole.AUTHOR)
    return _login(client, email)


def _create(client: TestClient, token: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Understanding the Future of Digital Publishing",
        "content": "A draft about publishing.",
        "excerpt": "A short summary",
    }
    payload.update(overrides)
    response = client.post("/api/v1/posts", headers=_auth(token), json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_reader_and_anonymous_cannot_create(client: TestClient) -> None:
    anonymous = client.post("/api/v1/posts", json={"title": "Hello World Today"})
    assert anonymous.status_code == 401

    _register(client, "Reader", "reader.posts@example.com")
    _promote("reader.posts@example.com", UserRole.READER)
    token = _login(client, "reader.posts@example.com")
    rejected = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={"title": "Hello World Today", "author_id": "not-the-caller"},
    )
    assert rejected.status_code == 403


def test_author_creates_a_draft_from_the_token(client: TestClient) -> None:
    token = _author(client)
    rejected = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={"title": "   ", "content": "Body"},
    )
    assert rejected.status_code == 422

    created = _create(client, token)
    assert created["slug"] == "understanding-the-future-of-digital-publishing"
    assert created["status"] == "draft"
    assert "hashed_password" not in created
    assert created["author"]["username"] == "Ada"
    assert "email" not in created["author"]

    public = client.get("/api/v1/posts")
    assert public.status_code == 200
    assert public.json()["total"] == 0
    hidden = client.get(f"/api/v1/posts/{created['slug']}")
    assert hidden.status_code == 404


def test_owner_updates_and_revisions_stay_sequential(client: TestClient) -> None:
    token = _author(client)
    created = _create(client, token)
    post_id = created["id"]

    first = client.patch(
        f"/api/v1/posts/{post_id}",
        headers=_auth(token),
        json={"title": "A Revised Publishing Title", "content": "Second body"},
    )
    assert first.status_code == 200
    second = client.patch(
        f"/api/v1/posts/{post_id}",
        headers=_auth(token),
        json={"content": "Third body"},
    )
    assert second.status_code == 200

    revisions = client.get(f"/api/v1/posts/{post_id}/revisions", headers=_auth(token))
    assert revisions.status_code == 200
    history = revisions.json()
    assert [item["revision_number"] for item in history] == [1, 2]
    assert history[0]["title"] == "Understanding the Future of Digital Publishing"
    assert history[0]["content"] == "A draft about publishing."
    assert history[1]["content"] == "Second body"

    one = client.get(
        f"/api/v1/posts/{post_id}/revisions/{history[0]['id']}",
        headers=_auth(token),
    )
    assert one.status_code == 200
    assert one.json()["revision_number"] == 1


def test_publish_unpublish_archive_and_delete_visibility(client: TestClient) -> None:
    token = _author(client)
    other = _author(client, "Grace", "grace.posts@example.com")
    created = _create(client, token, content="")
    post_id = str(created["id"])
    slug = str(created["slug"])

    empty = client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(token))
    assert empty.status_code == 422
    client.patch(
        f"/api/v1/posts/{post_id}",
        headers=_auth(token),
        json={"content": "Ready to publish."},
    )
    forbidden = client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(other))
    assert forbidden.status_code == 404

    published = client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(token))
    assert published.status_code == 200
    assert published.json()["published_at"] is not None
    assert client.get(f"/api/v1/posts/{slug}").status_code == 200
    assert client.get("/api/v1/posts").json()["total"] == 1

    unpublished = client.post(
        f"/api/v1/posts/{post_id}/unpublish", headers=_auth(token)
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["status"] == "draft"
    assert client.get(f"/api/v1/posts/{slug}").status_code == 404

    client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(token))
    archived = client.post(f"/api/v1/posts/{post_id}/archive", headers=_auth(token))
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.get(f"/api/v1/posts/{slug}").status_code == 404
    mine = client.get(f"/api/v1/posts/mine/{post_id}", headers=_auth(token))
    assert mine.status_code == 200

    deleted = client.delete(f"/api/v1/posts/{post_id}", headers=_auth(token))
    assert deleted.status_code == 204
    assert (
        client.get(f"/api/v1/posts/mine/{post_id}", headers=_auth(token)).status_code
        == 404
    )
    assert client.get("/api/v1/posts").json()["total"] == 0


def test_duplicate_titles_and_slug_redirect(client: TestClient) -> None:
    token = _author(client)
    first = _create(client, token, content="First article body")
    second = _create(client, token, content="Second article body")
    assert second["slug"] == "understanding-the-future-of-digital-publishing-2"

    published = client.post(
        f"/api/v1/posts/{first['id']}/publish", headers=_auth(token)
    )
    assert published.status_code == 200
    renamed = client.patch(
        f"/api/v1/posts/{first['id']}",
        headers=_auth(token),
        json={"slug": "future-of-publishing"},
    )
    assert renamed.status_code == 200
    old = client.get(f"/api/v1/posts/{first['slug']}", follow_redirects=False)
    assert old.status_code == 301
    assert old.headers["location"].endswith("/api/v1/posts/future-of-publishing")
    assert client.get("/api/v1/posts/future-of-publishing").status_code == 200


def test_public_search_pagination_and_filters(client: TestClient) -> None:
    token = _author(client)
    for number in range(1, 4):
        created = _create(
            client,
            token,
            title=f"Searchable Article {number}",
            content="alpha" if number == 2 else "beta",
            is_featured=number == 1,
        )
        assert (
            client.post(
                f"/api/v1/posts/{created['id']}/publish",
                headers=_auth(token),
            ).status_code
            == 200
        )

    page = client.get("/api/v1/posts", params={"page": 1, "page_size": 2})
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 2
    assert client.get("/api/v1/posts", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/posts", params={"page_size": 101}).status_code == 422

    found = client.get("/api/v1/posts", params={"search": "alpha"})
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["title"] == "Searchable Article 2"

    featured = client.get("/api/v1/posts", params={"featured": True})
    assert featured.json()["total"] == 1
    author_id = featured.json()["items"][0]["author"]["id"]
    by_author = client.get("/api/v1/posts", params={"author_id": author_id})
    assert by_author.json()["total"] == 3
    missing = client.get("/api/v1/posts/not-a-real-article")
    assert missing.status_code == 404


def test_administrator_can_manage_articles_others_cannot(client: TestClient) -> None:
    author_token = _author(client)
    created = _create(client, author_token)
    _register(client, "Admin", "admin.posts@example.com")
    _promote("admin.posts@example.com", UserRole.ADMIN)
    admin = _login(client, "admin.posts@example.com")
    _register(client, "Other", "other.posts@example.com")
    _promote("other.posts@example.com", UserRole.AUTHOR)
    other = _login(client, "other.posts@example.com")

    denied = client.get("/api/v1/posts/admin/all", headers=_auth(author_token))
    assert denied.status_code == 403
    listed = client.get(
        "/api/v1/posts/admin/all", headers=_auth(admin), params={"status": "draft"}
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    changed = client.patch(
        f"/api/v1/posts/{created['id']}",
        headers=_auth(admin),
        json={"excerpt": "Edited by an administrator"},
    )
    assert changed.status_code == 200
    blocked = client.patch(
        f"/api/v1/posts/{created['id']}",
        headers=_auth(other),
        json={"excerpt": "Not allowed"},
    )
    assert blocked.status_code == 404
    revisions = client.get(
        f"/api/v1/posts/{created['id']}/revisions", headers=_auth(other)
    )
    assert revisions.status_code == 404
    admin_history = client.get(
        f"/api/v1/posts/{created['id']}/revisions",
        headers=_auth(admin),
    )
    assert admin_history.status_code == 200
    assert admin_history.json()[0]["excerpt"] == "A short summary"


def test_unverified_author_cannot_publish(client: TestClient) -> None:
    _register(client, "Nova", "nova.posts@example.com")
    _promote("nova.posts@example.com", UserRole.AUTHOR, verified=False)
    token = _login(client, "nova.posts@example.com")
    response = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={"title": "Unverified Draft Title", "content": "Body"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Email verification is required."
