"""Search, discovery, related articles, suggestions, and view counting."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database.session import get_session_factory
from app.models.article_view import ArticleView
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
    assert response.status_code == 201, response.text


def _promote(email: str, role: UserRole) -> None:
    database = get_session_factory()()
    try:
        user = database.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = role
        user.is_verified = True
        database.commit()
    finally:
        database.close()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user(client: TestClient, username: str, email: str, role: UserRole) -> str:
    _register(client, username, email)
    _promote(email, role)
    return _login(client, email)


def _publish(client: TestClient, token: str, title: str, **extra: object) -> dict:
    created = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={"title": title, "content": "A readable public article.", **extra},
    )
    assert created.status_code == 201, created.text
    published = client.post(
        f"/api/v1/posts/{created.json()['id']}/publish",
        headers=_auth(token),
    )
    assert published.status_code == 200, published.text
    return published.json()


def _publication(client: TestClient, token: str, name: str, slug: str, **extra: object) -> dict:
    response = client.post(
        "/api/v1/publications",
        headers=_auth(token),
        json={"name": name, "slug": slug, "requires_review": False, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _view_rows() -> int:
    database = get_session_factory()()
    try:
        total = database.scalar(select(func.count()).select_from(ArticleView))
        return int(total or 0)
    finally:
        database.close()


def test_search_matches_title_body_partial_and_typo(client: TestClient) -> None:
    author = _user(client, "SearchAda", "search.ada@example.com", UserRole.AUTHOR)
    _publish(
        client,
        author,
        "Digital Gardens",
        content="A field guide to city planting.",
    )
    _publish(
        client,
        author,
        "Publishing Notes",
        content="The lanternfish crossed the trench.",
    )

    title = client.get("/api/v1/search", params={"q": "Digital Gardens", "type": "articles"})
    assert title.status_code == 200, title.text
    assert [item["title"] for item in title.json()["articles"]["items"]] == ["Digital Gardens"]
    assert "content" not in title.json()["articles"]["items"][0]
    assert "email" not in title.json()["articles"]["items"][0]["author"]

    body = client.get("/api/v1/search", params={"q": "lanternfish", "type": "articles"})
    assert [item["title"] for item in body.json()["articles"]["items"]] == ["Publishing Notes"]

    partial = client.get("/api/v1/search", params={"q": "digi", "type": "articles"})
    assert [item["title"] for item in partial.json()["articles"]["items"]] == ["Digital Gardens"]

    typo = client.get("/api/v1/search", params={"q": "Publshing", "type": "articles"})
    assert [item["title"] for item in typo.json()["articles"]["items"]] == ["Publishing Notes"]

    renamed = client.patch(
        "/api/v1/users/me",
        headers=_auth(author),
        json={"full_name": "Ada Searcher"},
    )
    assert renamed.status_code == 200, renamed.text
    by_name = client.get("/api/v1/search", params={"q": "Searcher", "type": "articles"})
    assert by_name.json()["articles"]["total"] == 2


def test_search_filters_pagination_and_sort(client: TestClient) -> None:
    admin = _user(client, "SearchAdmin", "search.admin@example.com", UserRole.ADMIN)
    author = _user(client, "SearchBen", "search.ben@example.com", UserRole.AUTHOR)
    category = client.post(
        "/api/v1/categories",
        headers=_auth(admin),
        json={"name": "Botany"},
    )
    assert category.status_code == 201, category.text
    tag = client.post("/api/v1/tags", headers=_auth(author), json={"name": "Kelp"})
    assert tag.status_code == 201, tag.text
    publication = _publication(client, author, "Open Desk", "open-desk")
    first = _publish(client, author, "First Dispatch", content="Shared dispatch wording.")
    second = _publish(
        client,
        author,
        "Second Dispatch",
        content="Shared dispatch wording.",
        category_id=category.json()["id"],
        tag_ids=[tag.json()["id"]],
        publication_id=publication["id"],
    )
    assert second["publication_id"] == publication["id"]

    filtered = client.get(
        "/api/v1/search",
        params={
            "q": "dispatch",
            "type": "articles",
            "category": category.json()["slug"],
            "tag": tag.json()["slug"],
            "author": "searchben",
            "publication": "open-desk",
            "date_from": "2000-01-01T00:00:00Z",
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["title"] for item in filtered.json()["articles"]["items"]] == ["Second Dispatch"]

    mismatched = client.get(
        "/api/v1/search",
        params={"q": "dispatch", "type": "articles", "author": "searchada"},
    )
    assert mismatched.json()["articles"]["total"] == 0

    future = client.get(
        "/api/v1/search",
        params={"q": "dispatch", "type": "articles", "date_from": "2999-01-01T00:00:00Z"},
    )
    assert future.json()["articles"]["total"] == 0

    newest = client.get(
        "/api/v1/search",
        params={"q": "dispatch", "type": "articles", "sort": "newest", "page_size": 1},
    )
    oldest = client.get(
        "/api/v1/search",
        params={"q": "dispatch", "type": "articles", "sort": "oldest", "page_size": 1, "page": 1},
    )
    assert newest.json()["articles"]["items"][0]["id"] != oldest.json()["articles"]["items"][0]["id"]
    page_two = client.get(
        "/api/v1/search",
        params={"q": "dispatch", "type": "articles", "sort": "newest", "page_size": 1, "page": 2},
    )
    assert page_two.json()["articles"]["total"] == 2
    assert page_two.json()["articles"]["items"][0]["id"] == oldest.json()["articles"]["items"][0]["id"]
    assert first["id"] in {
        newest.json()["articles"]["items"][0]["id"],
        page_two.json()["articles"]["items"][0]["id"],
    }

    renamed = client.patch(
        f"/api/v1/publications/{publication['id']}",
        headers=_auth(author),
        json={"name": "City Desk"},
    )
    assert renamed.status_code == 200, renamed.text
    by_publication = client.get("/api/v1/search", params={"q": "City Desk", "type": "articles"})
    assert [item["title"] for item in by_publication.json()["articles"]["items"]] == [
        "Second Dispatch"
    ]


def test_search_empty_and_invalid_queries(client: TestClient) -> None:
    author = _user(client, "SearchCora", "search.cora@example.com", UserRole.AUTHOR)
    _publish(client, author, "Visible Dispatch")
    client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Draft Dispatch", "content": "Still private."},
    )

    empty = client.get("/api/v1/search")
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert [item["title"] for item in body["articles"]["items"]] == ["Visible Dispatch"]
    assert body["authors"]["total"] == 0
    assert body["publications"]["total"] == 0

    punctuation = client.get("/api/v1/search", params={"q": "???"})
    assert punctuation.json()["articles"]["total"] == 0

    assert client.get("/api/v1/search", params={"q": "x" * 201}).status_code == 422
    assert client.get("/api/v1/search", params={"sort": "rank"}).status_code == 422
    assert client.get("/api/v1/search", params={"type": "users"}).status_code == 422
    invalid_dates = client.get(
        "/api/v1/search",
        params={"date_from": "2026-12-01T00:00:00Z", "date_to": "2020-01-01T00:00:00Z"},
    )
    assert invalid_dates.status_code == 422


def test_search_hides_unpublished_and_inaccessible_articles(client: TestClient) -> None:
    admin = _user(client, "HideAdmin", "hide.admin@example.com", UserRole.ADMIN)
    author = _user(client, "HideAda", "hide.ada@example.com", UserRole.AUTHOR)
    visible = _publish(client, author, "Independent Dispatch")
    draft = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Hidden Draft Title", "content": "Not ready."},
    )
    assert draft.status_code == 201
    archived = _publish(client, author, "Archived Dispatch")
    assert client.post(
        f"/api/v1/posts/{archived['id']}/archive", headers=_auth(author)
    ).status_code == 200
    deleted = _publish(client, author, "Deleted Dispatch")
    assert client.delete(
        f"/api/v1/posts/{deleted['id']}", headers=_auth(author)
    ).status_code == 204

    private = _publication(
        client, author, "Quiet Press", "quiet-press", visibility="private"
    )
    private_article = _publish(
        client,
        author,
        "Private Dispatch",
        publication_id=private["id"],
    )
    suspended = _publication(client, author, "Paused Press", "paused-press")
    _publish(client, author, "Suspended Dispatch", publication_id=suspended["id"])
    assert client.patch(
        f"/api/v1/publications/{suspended['id']}",
        headers=_auth(admin),
        json={"status": "suspended"},
    ).status_code == 200
    closed = _publication(client, author, "Closed Press", "closed-press")
    _publish(client, author, "Closed Dispatch", publication_id=closed["id"])
    assert client.post(
        f"/api/v1/publications/{closed['id']}/archive", headers=_auth(author)
    ).status_code == 200

    found = client.get("/api/v1/search", params={"q": "Dispatch", "type": "articles"})
    assert [item["title"] for item in found.json()["articles"]["items"]] == [
        "Independent Dispatch"
    ]
    public = client.get(f"/api/v1/posts/{visible['slug']}")
    assert public.status_code == 200
    assert client.get(f"/api/v1/posts/{private_article['slug']}").status_code == 404
    suggestions = client.get("/api/v1/search/suggestions", params={"q": "hidden"})
    assert suggestions.status_code == 200
    assert suggestions.json()["items"] == []
    private_name = client.get("/api/v1/search/suggestions", params={"q": "quiet"})
    assert private_name.json()["items"] == []


def test_discovery_lists_and_related_articles(client: TestClient) -> None:
    admin = _user(client, "DiscoverAdmin", "discover.admin@example.com", UserRole.ADMIN)
    author = _user(client, "DiscoverAda", "discover.ada@example.com", UserRole.AUTHOR)
    other = _user(client, "DiscoverBen", "discover.ben@example.com", UserRole.AUTHOR)
    reader = _user(client, "DiscoverReader", "discover.reader@example.com", UserRole.READER)
    category = client.post(
        "/api/v1/categories", headers=_auth(admin), json={"name": "Oceans"}
    )
    assert category.status_code == 201, category.text
    publication = _publication(client, author, "Harbor Review", "harbor-review")
    featured = _publish(
        client,
        author,
        "Featured Tide",
        is_featured=True,
        category_id=category.json()["id"],
        publication_id=publication["id"],
    )
    discussed = _publish(client, author, "Discussed Tide", category_id=category.json()["id"])
    plain = _publish(client, other, "Plain Tide")
    comment = client.post(
        f"/api/v1/posts/{discussed['id']}/comments",
        headers=_auth(reader),
        json={"body": "This article raises a useful question."},
    )
    assert comment.status_code == 201, comment.text
    viewed = client.post(
        f"/api/v1/posts/{featured['slug']}/view",
        headers={"X-Visitor-Id": "visitor-one"},
    )
    assert viewed.status_code == 204, viewed.text

    latest = client.get("/api/v1/discovery/articles", params={"feed": "latest"})
    assert latest.status_code == 200, latest.text
    assert {item["title"] for item in latest.json()["items"]} == {
        "Featured Tide",
        "Discussed Tide",
        "Plain Tide",
    }
    featured_feed = client.get("/api/v1/discovery/articles", params={"feed": "featured"})
    assert [item["title"] for item in featured_feed.json()["items"]] == ["Featured Tide"]
    discussed_feed = client.get("/api/v1/discovery/articles", params={"feed": "discussed"})
    assert discussed_feed.json()["items"][0]["title"] == "Discussed Tide"
    assert discussed_feed.json()["items"][0]["comment_count"] == 1
    popular = client.get("/api/v1/discovery/articles", params={"feed": "popular"})
    assert popular.json()["items"][0]["title"] == "Featured Tide"
    assert popular.json()["items"][0]["view_count"] == 1
    trending = client.get("/api/v1/discovery/articles", params={"feed": "trending"})
    assert trending.status_code == 200, trending.text
    assert trending.json()["items"][0]["title"] == "Discussed Tide"

    authors = client.get("/api/v1/discovery/authors", params={"q": "discoverada"})
    assert authors.status_code == 200, authors.text
    assert authors.json()["items"][0]["username"] == "DiscoverAda"
    assert authors.json()["items"][0]["article_count"] == 2
    assert "Oceans" in authors.json()["items"][0]["categories"]
    assert "email" not in authors.json()["items"][0]

    publications = client.get("/api/v1/discovery/publications", params={"q": "harbor"})
    assert publications.json()["items"][0]["slug"] == "harbor-review"
    assert publications.json()["items"][0]["article_count"] == 1
    assert "contact_email" not in publications.json()["items"][0]
    assert "members" not in publications.json()["items"][0]

    related = client.get(f"/api/v1/posts/{featured['id']}/related")
    assert related.status_code == 200, related.text
    titles = [item["title"] for item in related.json()["items"]]
    assert featured["title"] not in titles
    assert titles[0] == "Discussed Tide"
    assert plain["title"] not in titles
    again = client.get(f"/api/v1/posts/{featured['id']}/related")
    assert [item["id"] for item in again.json()["items"]] == [
        item["id"] for item in related.json()["items"]
    ]
    limited = client.get(f"/api/v1/posts/{featured['id']}/related", params={"limit": 1})
    assert len(limited.json()["items"]) == 1
    draft = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Unpublished Tide", "content": "Not public.", "category_id": category.json()["id"]},
    )
    assert client.get(f"/api/v1/posts/{draft.json()['id']}/related").status_code == 404


def test_views_count_public_reads_once(client: TestClient) -> None:
    author = _user(client, "ViewAda", "view.ada@example.com", UserRole.AUTHOR)
    article = _publish(client, author, "Counted Article")
    draft = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Uncounted Draft", "content": "Private."},
    )
    assert client.post(
        f"/api/v1/posts/{draft.json()['slug']}/view",
        headers={"X-Visitor-Id": "visitor-draft"},
    ).status_code == 404
    assert _view_rows() == 0

    missing = client.post(f"/api/v1/posts/{article['slug']}/view")
    assert missing.status_code == 204
    assert _view_rows() == 0
    assert client.post(
        f"/api/v1/posts/{article['slug']}/view",
        headers={"X-Visitor-Id": "short"},
    ).status_code == 422
    owner = client.post(
        f"/api/v1/posts/{article['slug']}/view",
        headers={**_auth(author), "X-Visitor-Id": "visitor-owner"},
    )
    assert owner.status_code == 204
    assert _view_rows() == 0

    first = client.post(
        f"/api/v1/posts/{article['slug']}/view",
        headers={"X-Visitor-Id": "visitor-one"},
    )
    assert first.status_code == 204
    repeat = client.post(
        f"/api/v1/posts/{article['slug']}/view",
        headers={"X-Visitor-Id": "visitor-one"},
    )
    assert repeat.status_code == 204
    second = client.post(
        f"/api/v1/posts/{article['slug']}/view",
        headers={"X-Visitor-Id": "visitor-two"},
    )
    assert second.status_code == 204
    probe = client.post(
        f"/api/v1/posts/{article['slug']}/view",
        headers={"X-Visitor-Id": "visitor-probe", "User-Agent": "kube-probe"},
    )
    assert probe.status_code == 204
    assert _view_rows() == 2

    listed = client.get(
        "/api/v1/search",
        params={"q": "Counted", "type": "articles", "sort": "most_viewed"},
    )
    assert listed.json()["articles"]["items"][0]["view_count"] == 2


def test_suggestions_and_admin_stats(client: TestClient) -> None:
    admin = _user(client, "StatsAdmin", "stats.admin@example.com", UserRole.ADMIN)
    author = _user(client, "StatsAda", "stats.ada@example.com", UserRole.AUTHOR)
    reader = _user(client, "StatsReader", "stats.reader@example.com", UserRole.READER)
    _publish(client, author, "Digital Gardens")
    client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Secret Draft Title", "content": "Hidden."},
    )
    _publication(client, author, "Quiet Press", "quiet-press", visibility="private")
    client.post(
        "/api/v1/categories", headers=_auth(admin), json={"name": "Botany"}
    )

    found = client.get("/api/v1/search/suggestions", params={"q": "digi"})
    assert found.status_code == 200, found.text
    assert any(item["label"] == "Digital Gardens" for item in found.json()["items"])
    assert client.get("/api/v1/search/suggestions", params={"q": "secret"}).json()["items"] == []
    assert client.get("/api/v1/search/suggestions", params={"q": "quiet"}).json()["items"] == []
    assert client.get("/api/v1/search/suggestions", params={"q": "a"}).status_code == 422
    assert client.get("/api/v1/search/suggestions").status_code == 422
    botany = client.get("/api/v1/search/suggestions", params={"q": "bot"})
    assert any(item["type"] == "category" and item["label"] == "Botany" for item in botany.json()["items"])

    current = get_settings()
    client.app.dependency_overrides[get_settings] = lambda: current.model_copy(
        update={"auth_rate_limit_enabled": True, "suggestion_rate_limit_per_hour": 2}
    )
    assert client.get("/api/v1/search/suggestions", params={"q": "di"}).status_code == 200
    assert client.get("/api/v1/search/suggestions", params={"q": "di"}).status_code == 200
    limited = client.get("/api/v1/search/suggestions", params={"q": "di"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"]

    client.app.dependency_overrides[get_settings] = lambda: current
    searched = client.get("/api/v1/search", params={"q": "Digital", "type": "articles"})
    assert searched.status_code == 200
    forbidden = client.get("/api/v1/search/admin/stats", headers=_auth(reader))
    assert forbidden.status_code == 403
    stats = client.get("/api/v1/search/admin/stats", headers=_auth(admin))
    assert stats.status_code == 200, stats.text
    assert stats.json()["total"] >= 1
    assert "email" not in stats.text
    assert "user_id" not in stats.text

    schema = client.get("/api/v1/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/search" in schema.text
    assert "/api/v1/discovery/articles" in schema.text
    assert "/api/v1/search/suggestions" in schema.text
