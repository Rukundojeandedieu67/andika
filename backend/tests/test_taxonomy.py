"""Category, tag, and article taxonomy tests."""

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


def _author(client: TestClient, username: str, email: str) -> str:
    _register(client, username, email)
    _promote(email, UserRole.AUTHOR)
    return _login(client, email)


def _admin(client: TestClient) -> str:
    _register(client, "Admin", "admin.taxonomy@example.com")
    _promote("admin.taxonomy@example.com", UserRole.ADMIN)
    return _login(client, "admin.taxonomy@example.com")


def _reader(client: TestClient) -> str:
    _register(client, "Reader", "reader.taxonomy@example.com")
    _promote("reader.taxonomy@example.com", UserRole.READER)
    return _login(client, "reader.taxonomy@example.com")


def _category(client: TestClient, token: str, name: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"name": name}
    payload.update(extra)
    response = client.post("/api/v1/categories", headers=_auth(token), json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _tag(client: TestClient, token: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/tags", headers=_auth(token), json={"name": name}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _draft(client: TestClient, token: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "A Taxonomy Article Title",
        "content": "Enough content to publish this article.",
    }
    payload.update(overrides)
    response = client.post("/api/v1/posts", headers=_auth(token), json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _publish(client: TestClient, token: str, post_id: object) -> None:
    response = client.post(
        f"/api/v1/posts/{post_id}/publish", headers=_auth(token)
    )
    assert response.status_code == 200, response.text


def test_admin_creates_updates_and_rejects_duplicate_categories(client: TestClient) -> None:
    admin = _admin(client)
    created = _category(
        client, admin, "  Technology  ", description="Platform and tools"
    )
    assert created["slug"] == "technology"
    assert created["description"] == "Platform and tools"

    listed = client.get("/api/v1/categories")
    assert listed.status_code == 200
    assert listed.json()[0]["slug"] == "technology"

    detail = client.get("/api/v1/categories/technology")
    assert detail.status_code == 200
    assert detail.json()["description"] == "Platform and tools"

    renamed = client.patch(
        f"/api/v1/categories/{created['id']}",
        headers=_auth(admin),
        json={"description": "Updated description"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["description"] == "Updated description"

    duplicate = client.post(
        "/api/v1/categories",
        headers=_auth(admin),
        json={"name": "TECHNOLOGY"},
    )
    assert duplicate.status_code == 409


def test_category_slug_suffix_and_hierarchy_rules(client: TestClient) -> None:
    admin = _admin(client)
    parent = _category(client, admin, "Health")
    child = _category(client, admin, "Digital Health", parent_id=parent["id"])
    grandchild = _category(
        client, admin, "Remote Care", parent_id=child["id"]
    )
    too_deep = client.post(
        "/api/v1/categories",
        headers=_auth(admin),
        json={"name": "Wearables", "parent_id": grandchild["id"]},
    )
    assert too_deep.status_code == 409

    cycle = client.patch(
        f"/api/v1/categories/{parent['id']}",
        headers=_auth(admin),
        json={"parent_id": child["id"]},
    )
    assert cycle.status_code == 409

    self_parent = client.patch(
        f"/api/v1/categories/{parent['id']}",
        headers=_auth(admin),
        json={"parent_id": parent["id"]},
    )
    assert self_parent.status_code == 409

    first = _category(client, admin, "C++")
    second = _category(client, admin, "C")
    assert first["slug"] != second["slug"]

    tree = client.get("/api/v1/categories").json()
    health = next(item for item in tree if item["slug"] == "health")
    assert health["children"][0]["slug"] == "digital-health"
    assert health["children"][0]["children"][0]["slug"] == "remote-care"


def test_inactive_parent_hides_children_and_blocks_assignment(client: TestClient) -> None:
    admin = _admin(client)
    author = _author(client, "Ada", "ada.taxonomy@example.com")
    parent = _category(client, admin, "Science")
    child = _category(client, admin, "Physics", parent_id=parent["id"])
    hidden = client.patch(
        f"/api/v1/categories/admin/{parent['id']}/status",
        headers=_auth(admin),
        json={"is_active": False},
    )
    assert hidden.status_code == 200

    public = client.get("/api/v1/categories")
    assert public.json() == []
    assert client.get("/api/v1/categories/physics").status_code == 404

    draft = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Hidden Category Article", "category_id": child["id"]},
    )
    assert draft.status_code == 422

    admin_list = client.get("/api/v1/categories/admin/all", headers=_auth(admin))
    assert admin_list.json()["total"] == 2


def test_author_and_reader_cannot_manage_categories(client: TestClient) -> None:
    admin = _admin(client)
    author = _author(client, "Nia", "nia.taxonomy@example.com")
    reader = _reader(client)
    category = _category(client, admin, "Culture")

    for token in (author, reader):
        created = client.post(
            "/api/v1/categories", headers=_auth(token), json={"name": "Blocked"}
        )
        assert created.status_code == 403
        updated = client.patch(
            f"/api/v1/categories/{category['id']}",
            headers=_auth(token),
            json={"name": "Changed"},
        )
        assert updated.status_code == 403

    removed = client.delete(
        f"/api/v1/categories/admin/{category['id']}", headers=_auth(author)
    )
    assert removed.status_code == 403


def test_tags_are_created_by_authors_and_hidden_until_published(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.tags@example.com")
    reader = _reader(client)
    admin = _admin(client)
    tag = _tag(client, author, "  Artificial Intelligence ")
    assert tag["slug"] == "artificial-intelligence"

    duplicate = client.post(
        "/api/v1/tags",
        headers=_auth(author),
        json={"name": "artificial intelligence"},
    )
    assert duplicate.status_code == 409

    blocked = client.post(
        "/api/v1/tags", headers=_auth(reader), json={"name": "Readers Cannot"}
    )
    assert blocked.status_code == 403

    assert client.get("/api/v1/tags").json()["total"] == 0
    assert client.get("/api/v1/tags/artificial-intelligence").status_code == 404

    admin_page = client.get("/api/v1/tags/admin/all", headers=_auth(admin))
    assert admin_page.json()["total"] == 1

    renamed = client.patch(
        f"/api/v1/tags/admin/{tag['id']}",
        headers=_auth(admin),
        json={"description": "Models and systems"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["description"] == "Models and systems"

    similar = _tag(client, author, "AI")
    again = _tag(client, author, "A.I.")
    assert similar["slug"] != again["slug"]


def test_article_taxonomy_assignment_and_revisions(client: TestClient) -> None:
    admin = _admin(client)
    author = _author(client, "Ada", "ada.assign@example.com")
    other = _author(client, "Bea", "bea.assign@example.com")
    category = _category(client, admin, "Technology")
    other_category = _category(client, admin, "Health")
    first = _tag(client, author, "Python")
    second = _tag(client, author, "FastAPI")
    created = _draft(
        client,
        author,
        category_id=category["id"],
        tag_ids=[first["id"], first["id"], second["id"]],
    )
    assert created["category"]["slug"] == "technology"
    assert [item["slug"] for item in created["tags"]] == ["python", "fastapi"]

    missing_category = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Missing Category Article",
            "category_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert missing_category.status_code == 404

    missing_tag = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Missing Tag Article",
            "tag_ids": ["22222222-2222-2222-2222-222222222222"],
        },
    )
    assert missing_tag.status_code == 404

    names = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Named Taxonomy Article", "category_id": "technology"},
    )
    assert names.status_code == 422

    updated = client.patch(
        f"/api/v1/posts/{created['id']}",
        headers=_auth(author),
        json={"category_id": other_category["id"], "tag_ids": [second["id"]]},
    )
    assert updated.status_code == 200
    assert updated.json()["category"]["slug"] == "health"
    assert [item["slug"] for item in updated.json()["tags"]] == ["fastapi"]
    revisions = client.get(
        f"/api/v1/posts/{created['id']}/revisions", headers=_auth(author)
    )
    assert revisions.status_code == 200
    assert revisions.json() == []

    foreign = client.patch(
        f"/api/v1/posts/{created['id']}",
        headers=_auth(other),
        json={"tag_ids": []},
    )
    assert foreign.status_code == 404


def test_public_filters_exclude_unpublished_articles(client: TestClient) -> None:
    admin = _admin(client)
    author = _author(client, "Ada", "ada.filter@example.com")
    technology = _category(client, admin, "Technology")
    software = _category(client, admin, "Software Development", parent_id=technology["id"])
    health = _category(client, admin, "Health")
    python = _tag(client, author, "Python")
    design = _tag(client, author, "Design")

    published = _draft(
        client,
        author,
        title="Published Technology Python",
        content="Published body.",
        category_id=software["id"],
        tag_ids=[python["id"]],
    )
    _publish(client, author, published["id"])
    draft = _draft(
        client,
        author,
        title="Draft Technology Python",
        category_id=technology["id"],
        tag_ids=[python["id"]],
    )
    archived = _draft(
        client,
        author,
        title="Archived Technology Python",
        content="Archived body.",
        category_id=technology["id"],
        tag_ids=[python["id"], design["id"]],
    )
    _publish(client, author, archived["id"])
    client.post(f"/api/v1/posts/{archived['id']}/archive", headers=_auth(author))
    deleted = _draft(
        client,
        author,
        title="Deleted Technology Python",
        content="Deleted body.",
        category_id=health["id"],
        tag_ids=[python["id"]],
    )
    _publish(client, author, deleted["id"])
    client.delete(f"/api/v1/posts/{deleted['id']}", headers=_auth(author))

    combined = client.get("/api/v1/posts?category=technology&tag=python")
    assert combined.status_code == 200
    assert combined.json()["total"] == 1
    assert combined.json()["items"][0]["id"] == published["id"]

    by_child = client.get("/api/v1/categories/software-development/posts")
    assert by_child.json()["total"] == 1
    by_parent = client.get("/api/v1/categories/technology/posts")
    assert by_parent.json()["total"] == 1
    assert client.get("/api/v1/tags").json()["total"] == 1
    assert client.get("/api/v1/tags/python/posts").json()["total"] == 1
    assert client.get("/api/v1/tags/design").status_code == 404
    assert draft["status"] == "draft"


def test_deleting_taxonomy_keeps_articles(client: TestClient) -> None:
    admin = _admin(client)
    author = _author(client, "Ada", "ada.delete@example.com")
    parent = _category(client, admin, "Technology")
    child = _category(client, admin, "Software Development", parent_id=parent["id"])
    tag = _tag(client, author, "Python")
    created = _draft(
        client,
        author,
        category_id=child["id"],
        tag_ids=[tag["id"]],
        content="Body that stays.",
    )
    blocked = client.delete(
        f"/api/v1/categories/admin/{parent['id']}", headers=_auth(admin)
    )
    assert blocked.status_code == 409

    removed_child = client.delete(
        f"/api/v1/categories/admin/{child['id']}", headers=_auth(admin)
    )
    assert removed_child.status_code == 204
    article = client.get(f"/api/v1/posts/mine/{created['id']}", headers=_auth(author))
    assert article.status_code == 200
    assert article.json()["category"] is None

    removed_tag = client.delete(
        f"/api/v1/tags/admin/{tag['id']}", headers=_auth(admin)
    )
    assert removed_tag.status_code == 204
    article = client.get(f"/api/v1/posts/mine/{created['id']}", headers=_auth(author))
    assert article.json()["title"] == "A Taxonomy Article Title"
    assert article.json()["tags"] == []
