"""Author, publication, and administrator analytics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import get_session_factory
from app.models.article_view import ArticleView
from app.models.post import Post
from app.models.user import User, UserRole
from app.services import analytics_service
from app.services.analytics_service import (
    EXPORT_ROW_LIMIT,
    average_views,
    csv_cell,
    engagement_rate,
)

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


def _reader(client: TestClient, username: str, email: str) -> str:
    return _user(client, username, email, UserRole.READER)


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


def _view(client: TestClient, slug: str, visitor: str, token: str | None = None) -> None:
    headers = {"X-Visitor-Id": visitor}
    if token is not None:
        headers.update(_auth(token))
    response = client.post(f"/api/v1/posts/{slug}/view", headers=headers)
    assert response.status_code == 204, response.text


def _comment(client: TestClient, token: str, post_id: str, body: str) -> dict:
    response = client.post(
        f"/api/v1/posts/{post_id}/comments",
        headers=_auth(token),
        json={"body": body},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _invite(client: TestClient, token: str, publication_id: str, email: str, role: str) -> None:
    response = client.post(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(token),
        json={"email": email, "role": role},
    )
    assert response.status_code == 201, response.text


def _token_for(client: TestClient, email: str) -> str:
    matches = [
        item
        for item in client.mailbox.messages  # type: ignore[attr-defined]
        if item["template"] == "publication_invitation" and item["recipient"] == email
    ]
    assert matches
    return str(matches[-1]["body"].split("#token=", 1)[1].split()[0].strip())


def _join(client: TestClient, owner: str, publication_id: str, username: str, email: str, role: str) -> str:
    token = _reader(client, username, email)
    _invite(client, owner, publication_id, email, role)
    accepted = client.post(
        "/api/v1/invitations/accept",
        headers=_auth(token),
        json={"token": _token_for(client, email)},
    )
    assert accepted.status_code == 200, accepted.text
    return token


def _membership(client: TestClient, token: str, publication_id: str, username: str) -> str:
    response = client.get(
        f"/api/v1/publications/{publication_id}/members",
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    for item in response.json()["items"]:
        if item["user"]["username"] == username:
            return str(item["id"])
    raise AssertionError(username)


def test_engagement_formulas_are_zero_safe() -> None:
    assert engagement_rate(1, 2) == 50.0
    assert engagement_rate(1, 0) == 0.0
    assert average_views(3, 2) == 1.5
    assert average_views(3, 0) == 0.0
    assert csv_cell("=1+1") == "'=1+1"
    assert csv_cell("+1") == "'+1"
    assert csv_cell("-1") == "'-1"
    assert csv_cell("@cmd") == "'@cmd"
    assert csv_cell("\t=1") == "'\t=1"
    assert csv_cell("\r=1") == "'\r=1"
    assert csv_cell("Safe Title") == "Safe Title"
    assert csv_cell(None) == ""
    assert csv_cell(4) == "4"


def test_author_overview_counts_own_published_work(client: TestClient) -> None:
    author = _user(client, "Ada", "ada.analytics@example.com", UserRole.AUTHOR)
    other = _user(client, "Bea", "bea.analytics@example.com", UserRole.AUTHOR)
    reader = _reader(client, "Rae", "rae.analytics@example.com")
    _register(client, "Una", "una.analytics@example.com")
    unverified = _login(client, "una.analytics@example.com")
    publication = _publication(client, author, "Ada Journal", "ada-journal")

    independent = _publish(client, author, "Independent Essay")
    journal = _publish(client, author, "Journal Essay", publication_id=publication["id"])
    draft = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Draft Essay", "content": "Still private."},
    )
    assert draft.status_code == 201, draft.text
    archived = _publish(client, author, "Archived Essay")
    deleted = _publish(client, author, "Deleted Essay")
    other_article = _publish(client, other, "Bea Essay")

    hidden_view = client.post(
        f"/api/v1/posts/{draft.json()['slug']}/view",
        headers={"X-Visitor-Id": "visitor-draft"},
    )
    assert hidden_view.status_code == 404
    _view(client, independent["slug"], "visitor-one1")
    _view(client, independent["slug"], "visitor-one1")
    _view(client, independent["slug"], "visitor-two2")
    _view(client, independent["slug"], "visitor-self", author)
    _view(client, journal["slug"], "visitor-three")
    _view(client, archived["slug"], "visitor-arch1")
    _view(client, deleted["slug"], "visitor-gone1")
    _view(client, other_article["slug"], "visitor-bea01")
    archived_response = client.post(
        f"/api/v1/posts/{archived['id']}/archive", headers=_auth(author)
    )
    assert archived_response.status_code == 200, archived_response.text
    removed = client.delete(f"/api/v1/posts/{deleted['id']}", headers=_auth(author))
    assert removed.status_code == 204, removed.text

    approved = _comment(client, reader, independent["id"], "A careful public note.")
    assert approved["status"] == "approved"
    pending = _comment(client, unverified, independent["id"], "Waiting for review.")
    assert pending["status"] == "pending"
    _comment(client, reader, journal["id"], "A second public note.")

    guest = client.get("/api/v1/analytics/author/overview")
    assert guest.status_code == 401
    blocked = client.get("/api/v1/analytics/author/overview", headers=_auth(unverified))
    assert blocked.status_code == 403

    overview = client.get("/api/v1/analytics/author/overview", headers=_auth(author))
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["published_articles"] == 2
    assert body["publication_articles"] == 1
    assert body["total_views"] == 3
    assert body["total_approved_comments"] == 2
    assert body["period_views"] == 3
    assert body["period_approved_comments"] == 2
    assert body["average_views_per_article"] == 1.5
    assert body["comparison"] is None
    assert "not unique readers" in " ".join(body["limitations"])

    articles = client.get(
        "/api/v1/analytics/author/articles",
        headers=_auth(author),
        params={"sort": "views"},
    )
    assert articles.status_code == 200, articles.text
    page = articles.json()
    assert page["total"] == 2
    assert [item["title"] for item in page["items"]] == ["Independent Essay", "Journal Essay"]
    assert page["items"][0]["views"] == 2
    assert page["items"][0]["approved_comments"] == 1
    assert page["items"][0]["engagement_rate"] == 50.0
    assert page["items"][0]["publication"] is None
    assert page["items"][1]["views"] == 1
    assert page["items"][1]["engagement_rate"] == 100.0
    assert page["items"][1]["publication"]["slug"] == "ada-journal"
    first_page = client.get(
        "/api/v1/analytics/author/articles",
        headers=_auth(author),
        params={"sort": "views", "page": 1, "page_size": 1},
    )
    assert first_page.json()["total"] == 2
    assert len(first_page.json()["items"]) == 1
    newest = client.get(
        "/api/v1/analytics/author/articles",
        headers=_auth(author),
        params={"sort": "published_at"},
    )
    assert newest.json()["items"][0]["title"] == "Journal Essay"
    invalid = client.get(
        "/api/v1/analytics/author/articles",
        headers=_auth(author),
        params={"sort": "rank"},
    )
    assert invalid.status_code == 422

    other_overview = client.get("/api/v1/analytics/author/overview", headers=_auth(other))
    assert other_overview.status_code == 200, other_overview.text
    assert other_overview.json()["published_articles"] == 1
    assert other_overview.json()["total_views"] == 1
    assert other_overview.json()["publication_articles"] == 0
    other_titles = client.get("/api/v1/analytics/author/articles", headers=_auth(other)).json()
    assert [item["title"] for item in other_titles["items"]] == ["Bea Essay"]

    empty = client.get(
        "/api/v1/analytics/author/overview",
        headers=_auth(author),
        params={"date_from": "2099-01-01T00:00:00Z", "date_to": "2099-01-03T00:00:00Z"},
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["published_articles"] == 2
    assert empty.json()["period_views"] == 0
    assert empty.json()["period_approved_comments"] == 0

    deleted_comment = client.delete(
        f"/api/v1/comments/{approved['id']}",
        headers=_auth(reader),
    )
    assert deleted_comment.status_code == 204, deleted_comment.text
    after_delete = client.get("/api/v1/analytics/author/overview", headers=_auth(author))
    assert after_delete.json()["total_approved_comments"] == 1


def test_author_timeseries_comparisons_and_date_rules(client: TestClient) -> None:
    author = _user(client, "Cara", "cara.analytics@example.com", UserRole.AUTHOR)
    older = _publish(client, author, "Older Dispatch")
    _view(client, older["slug"], "visitor-old01")
    database = get_session_factory()()
    try:
        post = database.scalar(select(Post).where(Post.slug == older["slug"]))
        assert post is not None
        post.published_at = datetime.now(UTC) - timedelta(days=45)
        view = database.scalar(select(ArticleView).where(ArticleView.post_id == post.id))
        assert view is not None
        view.viewed_at = post.published_at
        database.commit()
    finally:
        database.close()
    current = _publish(client, author, "Current Dispatch")
    _view(client, current["slug"], "visitor-new01")

    compared = client.get(
        "/api/v1/analytics/author/overview",
        headers=_auth(author),
        params={"compare": "true"},
    )
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["published_articles"] == 2
    assert body["total_views"] == 2
    assert body["period_views"] == 1
    assert body["comparison"]["views"] == 1
    assert body["comparison"]["articles_published"] == 1
    assert body["comparison"]["approved_comments"] == 0

    series = client.get("/api/v1/analytics/author/timeseries", headers=_auth(author))
    assert series.status_code == 200, series.text
    points = series.json()["points"]
    assert series.json()["timezone"] == "UTC"
    assert series.json()["week_starts_on"] == "monday"
    assert sum(point["views"] for point in points) == 1
    assert sum(point["articles_published"] for point in points) == 1
    assert any(point["views"] == 0 for point in points)

    weekly = client.get(
        "/api/v1/analytics/author/timeseries",
        headers=_auth(author),
        params={"period": "week"},
    )
    assert weekly.status_code == 200, weekly.text
    assert sum(point["views"] for point in weekly.json()["points"]) == 1

    quiet = client.get(
        "/api/v1/analytics/author/timeseries",
        headers=_auth(author),
        params={
            "date_from": "2024-01-01T00:00:00Z",
            "date_to": "2024-01-14T00:00:00Z",
            "period": "week",
        },
    )
    assert quiet.status_code == 200, quiet.text
    assert [point["bucket_start"] for point in quiet.json()["points"]] == [
        "2024-01-01",
        "2024-01-08",
    ]
    assert all(point["views"] == 0 and point["articles_published"] == 0 for point in quiet.json()["points"])

    months = client.get(
        "/api/v1/analytics/author/timeseries",
        headers=_auth(author),
        params={
            "date_from": "2024-01-15T00:00:00Z",
            "date_to": "2024-03-02T00:00:00Z",
            "period": "month",
        },
    )
    assert [point["bucket_start"] for point in months.json()["points"]] == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
    ]

    reversed_dates = client.get(
        "/api/v1/analytics/author/overview",
        headers=_auth(author),
        params={"date_from": "2024-05-02T00:00:00Z", "date_to": "2024-05-01T00:00:00Z"},
    )
    assert reversed_dates.status_code == 422
    assert "date_from" in reversed_dates.json()["error"]["message"]
    too_long = client.get(
        "/api/v1/analytics/author/overview",
        headers=_auth(author),
        params={"date_from": "2020-01-01T00:00:00Z", "date_to": "2021-02-01T00:00:00Z"},
    )
    assert too_long.status_code == 422
    assert "366" in too_long.json()["error"]["message"]
    bad_period = client.get(
        "/api/v1/analytics/author/timeseries",
        headers=_auth(author),
        params={"period": "year"},
    )
    assert bad_period.status_code == 422


def test_publication_analytics_follow_membership(client: TestClient) -> None:
    owner = _user(client, "Nia", "nia.analytics@example.com", UserRole.AUTHOR)
    publication = _publication(client, owner, "City Desk", "city-desk")
    publication_id = publication["id"]
    editor = _join(client, owner, publication_id, "Eden", "eden.analytics@example.com", "editor")
    writer = _join(client, owner, publication_id, "Wren", "wren.analytics@example.com", "author")
    helper = _join(client, owner, publication_id, "Hope", "hope.analytics@example.com", "contributor")
    outsider = _reader(client, "Otto", "otto.analytics@example.com")
    admin = _user(client, "AdaAdmin", "admin.analytics@example.com", UserRole.ADMIN)

    owner_article = _publish(client, owner, "Owner Piece", publication_id=publication_id)
    independent = _publish(client, owner, "Owner Independent")
    writer_article = _publish(client, writer, "Writer Piece", publication_id=publication_id)
    helper_draft = client.post(
        "/api/v1/posts",
        headers=_auth(helper),
        json={
            "title": "Helper Piece",
            "content": "A contribution that needs an editor.",
            "publication_id": publication_id,
        },
    )
    assert helper_draft.status_code == 201, helper_draft.text
    denied_publish = client.post(
        f"/api/v1/posts/{helper_draft.json()['id']}/publish",
        headers=_auth(helper),
    )
    assert denied_publish.status_code == 403
    helper_article = client.post(
        f"/api/v1/posts/{helper_draft.json()['id']}/publish",
        headers=_auth(editor),
    )
    assert helper_article.status_code == 200, helper_article.text

    _view(client, writer_article["slug"], "visitor-wren1")
    _view(client, helper_article.json()["slug"], "visitor-hope1")
    _comment(client, editor, writer_article["id"], "An editor left a public note.")

    owner_report = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(owner),
    )
    assert owner_report.status_code == 200, owner_report.text
    owner_body = owner_report.json()
    assert owner_body["scope"] == "publication"
    assert owner_body["published_articles"] == 3
    assert owner_body["total_views"] == 2
    assert owner_body["total_approved_comments"] == 1
    assert owner_body["active_authors"] == 3
    assert owner_body["period_articles_published"] == 3
    assert owner_body["average_views_per_article"] == 0.67

    editor_report = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(editor),
    )
    assert editor_report.status_code == 200
    assert editor_report.json()["published_articles"] == 3
    editor_articles = client.get(
        f"/api/v1/analytics/publications/{publication_id}/articles",
        headers=_auth(editor),
    )
    titles = {item["title"] for item in editor_articles.json()["items"]}
    assert titles == {"Owner Piece", "Writer Piece", "Helper Piece"}
    assert independent["title"] not in titles
    editor_authors = client.get(
        f"/api/v1/analytics/publications/{publication_id}/authors",
        headers=_auth(editor),
        params={"page_size": 1},
    )
    assert editor_authors.status_code == 200, editor_authors.text
    assert editor_authors.json()["total"] == 3
    assert "@" not in editor_authors.text

    writer_report = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(writer),
    )
    assert writer_report.json()["scope"] == "own"
    assert writer_report.json()["published_articles"] == 1
    assert writer_report.json()["total_views"] == 1
    assert writer_report.json()["total_approved_comments"] == 1
    writer_articles = client.get(
        f"/api/v1/analytics/publications/{publication_id}/articles",
        headers=_auth(writer),
    )
    assert [item["title"] for item in writer_articles.json()["items"]] == ["Writer Piece"]
    writer_authors = client.get(
        f"/api/v1/analytics/publications/{publication_id}/authors",
        headers=_auth(writer),
    )
    assert [item["username"] for item in writer_authors.json()["items"]] == ["Wren"]

    helper_report = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(helper),
    )
    assert helper_report.json()["scope"] == "own"
    assert helper_report.json()["published_articles"] == 1
    assert helper_report.json()["total_views"] == 1
    assert helper_report.json()["total_approved_comments"] == 0
    helper_articles = client.get(
        f"/api/v1/analytics/publications/{publication_id}/articles",
        headers=_auth(helper),
    )
    assert [item["title"] for item in helper_articles.json()["items"]] == ["Helper Piece"]

    own_work = client.get("/api/v1/analytics/author/overview", headers=_auth(owner))
    assert own_work.json()["published_articles"] == 2
    assert own_work.json()["publication_articles"] == 1
    editor_has_no_articles = client.get("/api/v1/analytics/author/overview", headers=_auth(editor))
    assert editor_has_no_articles.json()["published_articles"] == 0
    writer_author = client.get("/api/v1/analytics/author/overview", headers=_auth(writer))
    assert writer_author.json()["published_articles"] == 1

    missing = client.get(
        f"/api/v1/analytics/publications/{owner_article['id']}/overview",
        headers=_auth(outsider),
    )
    assert missing.status_code == 404
    stranger = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(outsider),
    )
    assert stranger.status_code == 404
    admin_publication = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(admin),
    )
    assert admin_publication.status_code == 404
    assert client.get("/api/v1/analytics/admin/overview", headers=_auth(owner)).status_code == 403
    assert client.get("/api/v1/analytics/admin/overview", headers=_auth(admin)).status_code == 200

    helper_id = _membership(client, owner, publication_id, "Hope")
    suspended = client.post(
        f"/api/v1/publications/{publication_id}/members/{helper_id}/suspend",
        headers=_auth(owner),
    )
    assert suspended.status_code == 200, suspended.text
    assert (
        client.get(
            f"/api/v1/analytics/publications/{publication_id}/overview",
            headers=_auth(helper),
        ).status_code
        == 403
    )
    writer_id = _membership(client, owner, publication_id, "Wren")
    removed = client.post(
        f"/api/v1/publications/{publication_id}/members/{writer_id}/remove",
        headers=_auth(owner),
    )
    assert removed.status_code == 200, removed.text
    assert (
        client.get(
            f"/api/v1/analytics/publications/{publication_id}/articles",
            headers=_auth(writer),
        ).status_code
        == 403
    )
    still_there = client.get(
        f"/api/v1/analytics/publications/{publication_id}/overview",
        headers=_auth(editor),
    )
    assert still_there.json()["published_articles"] == 3


def test_admin_analytics_are_aggregated_and_private(client: TestClient) -> None:
    admin = _user(client, "Mina", "mina.analytics@example.com", UserRole.ADMIN)
    author = _user(client, "Omar", "omar.analytics@example.com", UserRole.AUTHOR)
    reader = _reader(client, "Lina", "lina.analytics@example.com")
    public = _publication(client, author, "Open Journal", "open-journal")
    private = _publication(
        client, author, "Closed Journal", "closed-journal", visibility="private"
    )
    independent = _publish(client, author, "Plain Dispatch")
    public_article = _publish(client, author, "Open Dispatch", publication_id=public["id"])
    secret = _publish(client, author, "Secret Ledger", publication_id=private["id"])
    _view(client, independent["slug"], "visitor-plain")
    _view(client, public_article["slug"], "visitor-open1")
    private_view = client.post(
        f"/api/v1/posts/{secret['slug']}/view",
        headers={"X-Visitor-Id": "visitor-secret"},
    )
    assert private_view.status_code == 404
    _comment(client, reader, public_article["id"], "A note on the public dispatch.")
    search = client.get("/api/v1/search", params={"q": "zzzz-not-a-title"})
    assert search.status_code == 200, search.text

    denied = client.get("/api/v1/analytics/admin/overview", headers=_auth(author))
    assert denied.status_code == 403
    assert client.get("/api/v1/analytics/admin/timeseries", headers=_auth(author)).status_code == 403
    assert client.get("/api/v1/analytics/admin/content", headers=_auth(author)).status_code == 403
    assert client.get("/api/v1/analytics/admin/export", headers=_auth(author)).status_code == 403
    private_report = client.get(
        f"/api/v1/analytics/publications/{private['id']}/overview",
        headers=_auth(reader),
    )
    assert private_report.status_code == 404
    owner_private = client.get(
        f"/api/v1/analytics/publications/{private['id']}/overview",
        headers=_auth(author),
    )
    assert owner_private.status_code == 200, owner_private.text
    assert owner_private.json()["published_articles"] == 1
    assert owner_private.json()["total_views"] == 0

    overview = client.get(
        "/api/v1/analytics/admin/overview",
        headers=_auth(admin),
        params={"compare": "true"},
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["registered_users"] == 3
    assert body["active_users"] == 3
    assert "last sign-in" in body["active_user_definition"]
    assert body["publications"] == 2
    assert body["active_public_publications"] == 1
    assert body["published_articles"] == 3
    assert body["total_views"] == 2
    assert body["total_approved_comments"] == 1
    assert body["period_registrations"] == 3
    assert body["period_articles_published"] == 3
    assert body["period_publications"] == 2
    assert body["comparison"]["registrations"] == 0
    assert body["comparison"]["views"] == 0
    assert "example.com" not in overview.text
    assert "zzzz-not-a-title" not in overview.text

    series = client.get("/api/v1/analytics/admin/timeseries", headers=_auth(admin))
    assert series.status_code == 200, series.text
    points = series.json()["points"]
    assert sum(point["registrations"] for point in points) == 3
    assert sum(point["publications_created"] for point in points) == 2
    assert sum(point["views"] for point in points) == 2
    assert sum(point["articles_published"] for point in points) == 3

    content = client.get("/api/v1/analytics/admin/content", headers=_auth(admin))
    assert content.status_code == 200, content.text
    payload = content.json()
    assert payload["independent"]["published_articles"] == 1
    assert payload["independent"]["views"] == 1
    assert payload["public_publication"]["published_articles"] == 1
    assert payload["public_publication"]["approved_comments"] == 1
    assert payload["public_publication"]["engagement_rate"] == 100.0
    assert payload["other_publication"]["published_articles"] == 1
    assert payload["other_publication"]["views"] == 0
    titles = [item["title"] for item in payload["top_public_articles"]]
    assert "Secret Ledger" not in titles
    assert "Secret Ledger" not in content.text
    assert "Open Dispatch" in titles
    assert "example.com" not in content.text
    assert "visitor_hash" not in content.text
    assert "zzzz-not-a-title" not in content.text

    exported = client.get("/api/v1/analytics/admin/export", headers=_auth(admin))
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    assert 'filename="andika-admin-analytics.csv"' in exported.headers["content-disposition"]
    assert "Secret Ledger" not in exported.text
    assert "example.com" not in exported.text
    assert "independent" in exported.text


def test_csv_exports_are_permissioned_and_formula_safe(client: TestClient) -> None:
    author = _user(client, "Ivo", "ivo.analytics@example.com", UserRole.AUTHOR)
    other = _user(client, "Noa", "noa.analytics@example.com", UserRole.AUTHOR)
    publication = _publication(client, author, "Formula Review", "formula-review")
    publication_id = publication["id"]
    _publish(client, author, "Safe Title", publication_id=publication_id)
    _publish(client, author, "=1+1", publication_id=publication_id)
    _publish(client, other, "Someone Else")

    exported = client.get("/api/v1/analytics/author/export", headers=_auth(author))
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    assert 'filename="andika-author-analytics.csv"' in exported.headers["content-disposition"]
    assert exported.headers["cache-control"] == "no-store"
    assert exported.headers["x-andika-export-truncated"] == "false"
    assert exported.headers["x-andika-export-limit"] == str(EXPORT_ROW_LIMIT)
    assert "'=1+1" in exported.text
    assert "Safe Title" in exported.text
    assert "Someone Else" not in exported.text
    assert "example.com" not in exported.text

    other_export = client.get("/api/v1/analytics/author/export", headers=_auth(other))
    assert "Someone Else" in other_export.text
    assert "Safe Title" not in other_export.text

    original = analytics_service.EXPORT_ROW_LIMIT
    analytics_service.EXPORT_ROW_LIMIT = 1
    try:
        truncated = client.get("/api/v1/analytics/author/export", headers=_auth(author))
    finally:
        analytics_service.EXPORT_ROW_LIMIT = original
    assert truncated.headers["x-andika-export-truncated"] == "true"
    assert truncated.text.count("\n") == 2
    assert "'=1+1" in truncated.text
    assert "Safe Title" not in truncated.text

    outsider = _reader(client, "Pia", "pia.analytics@example.com")
    hidden = client.get(
        f"/api/v1/analytics/publications/{publication_id}/export",
        headers=_auth(outsider),
    )
    assert hidden.status_code == 404
    publication_export = client.get(
        f"/api/v1/analytics/publications/{publication_id}/export",
        headers=_auth(author),
    )
    assert publication_export.status_code == 200, publication_export.text
    assert 'filename="andika-publication-analytics.csv"' in publication_export.headers[
        "content-disposition"
    ]
    assert "Ivo" in publication_export.text
    assert "example.com" not in publication_export.text
    assert "'=1+1" in publication_export.text
