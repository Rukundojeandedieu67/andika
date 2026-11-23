"""Publication membership, invitations, and editorial workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import get_session_factory
from app.models.publication import InvitationStatus, PublicationInvitation
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


def _verified_reader(client: TestClient, username: str, email: str) -> str:
    _register(client, username, email)
    _promote(email, UserRole.READER)
    return _login(client, email)


def _create_publication(client: TestClient, token: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"name": "North Review", "description": "A public journal"}
    payload.update(overrides)
    response = client.post("/api/v1/publications", headers=_auth(token), json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _invite(client: TestClient, token: str, publication_id: str, email: str, role: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(token),
        json={"email": email, "role": role},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _token_for(client: TestClient, email: str) -> str:
    matches = [
        item
        for item in client.mailbox.messages  # type: ignore[attr-defined]
        if item["template"] == "publication_invitation" and item["recipient"] == email
    ]
    assert matches
    return str(matches[-1]["body"].split("#token=", 1)[1].split()[0].strip())


def _accept(client: TestClient, token: str, raw_token: str) -> object:
    return client.post(
        "/api/v1/invitations/accept",
        headers=_auth(token),
        json={"token": raw_token},
    )


def _expire(email: str) -> None:
    database = get_session_factory()()
    try:
        invitation = database.scalar(
            select(PublicationInvitation).where(
                PublicationInvitation.email_key == email,
                PublicationInvitation.status == InvitationStatus.PENDING,
            )
        )
        assert invitation is not None
        invitation.expires_at = datetime.now(UTC) - timedelta(hours=1)
        database.commit()
    finally:
        database.close()


def test_verified_reader_opens_a_publication_without_a_platform_role(client: TestClient) -> None:
    guest = client.post("/api/v1/publications", json={"name": "Hidden Press"})
    assert guest.status_code == 401
    _register(client, "Nia", "nia.pub@example.com")
    unverified = _login(client, "nia.pub@example.com")
    blocked = client.post(
        "/api/v1/publications",
        headers=_auth(unverified),
        json={"name": "Hidden Press"},
    )
    assert blocked.status_code == 403

    token = _verified_reader(client, "NiaOwner", "nia.owner@example.com")
    created = _create_publication(client, token, slug="north-review")
    assert created["slug"] == "north-review"
    assert "email" not in created["owner"]
    profile = client.get("/api/v1/users/me", headers=_auth(token))
    assert profile.json()["role"] == "reader"

    duplicate = client.post(
        "/api/v1/publications",
        headers=_auth(token),
        json={"name": "Another Name", "slug": "north-review"},
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/publications", params={"search": "North"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    public = client.get("/api/v1/publications/north-review")
    assert public.status_code == 200
    assert public.json()["name"] == "North Review"

    outsider = _verified_reader(client, "Outsider", "outsider.pub@example.com")
    hidden = client.get(
        f"/api/v1/publications/{created['id']}/manage",
        headers=_auth(outsider),
    )
    assert hidden.status_code == 404
    manage = client.get(
        f"/api/v1/publications/{created['id']}/manage",
        headers=_auth(token),
    )
    assert manage.status_code == 200
    assert manage.json()["caller_role"] == "owner"
    assert manage.json()["requires_review"] is True


def test_private_and_archived_publications_stay_out_of_public_lists(client: TestClient) -> None:
    token = _verified_reader(client, "PrivateEd", "private.pub@example.com")
    private = _create_publication(
        client,
        token,
        name="Closed Journal",
        slug="closed-journal",
        visibility="private",
        requires_review=False,
    )
    assert client.get("/api/v1/publications/closed-journal").status_code == 404
    assert client.get("/api/v1/publications", params={"search": "Closed"}).json()["total"] == 0

    draft = client.post(
        "/api/v1/posts",
        headers=_auth(token),
        json={
            "title": "Members Only Dispatch",
            "content": "This stays inside the publication.",
            "publication_id": private["id"],
        },
    )
    assert draft.status_code == 201, draft.text
    published = client.post(
        f"/api/v1/posts/{draft.json()['id']}/publish",
        headers=_auth(token),
    )
    assert published.status_code == 200, published.text
    slug = published.json()["slug"]
    assert client.get(f"/api/v1/posts/{slug}").status_code == 404
    assert client.get("/api/v1/posts", params={"search": "Members Only"}).json()["total"] == 0
    assert client.get("/api/v1/publications/closed-journal/posts").status_code == 404
    comment = client.post(
        f"/api/v1/posts/{draft.json()['id']}/comments",
        headers=_auth(token),
        json={"body": "This note should stay private."},
    )
    assert comment.status_code == 404

    public = _create_publication(client, token, name="Open Ledger", slug="open-ledger")
    archived = client.post(
        f"/api/v1/publications/{public['id']}/archive",
        headers=_auth(token),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert client.get("/api/v1/publications/open-ledger").status_code == 404
    restored = client.post(
        f"/api/v1/publications/{public['id']}/restore",
        headers=_auth(token),
    )
    assert restored.status_code == 200, restored.text
    assert client.get("/api/v1/publications/open-ledger").status_code == 200


def test_membership_permissions_transfer_and_suspension(client: TestClient) -> None:
    owner = _verified_reader(client, "Owner", "owner.pub@example.com")
    publication = _create_publication(client, owner, slug="shared-desk")
    publication_id = str(publication["id"])
    editor_token = _verified_reader(client, "Editor", "editor.pub@example.com")
    author_token = _verified_reader(client, "Author", "author.pub@example.com")
    _invite(client, owner, publication_id, "editor.pub@example.com", "editor")
    _invite(client, owner, publication_id, "author.pub@example.com", "author")
    assert _accept(client, editor_token, _token_for(client, "editor.pub@example.com")).status_code == 200
    assert _accept(client, author_token, _token_for(client, "author.pub@example.com")).status_code == 200

    second = _create_publication(client, editor_token, name="Editor Journal", slug="editor-journal")
    mine = client.get("/api/v1/publications/mine", headers=_auth(editor_token))
    assert mine.status_code == 200
    assert mine.json()["total"] == 2
    assert {item["slug"] for item in mine.json()["items"]} == {"shared-desk", "editor-journal"}
    assert second["owner"]["username"] == "Editor"

    members = client.get(
        f"/api/v1/publications/{publication_id}/members",
        headers=_auth(owner),
    )
    assert members.status_code == 200
    by_name = {item["user"]["username"]: item for item in members.json()["items"]}
    assert "email" not in by_name["Editor"]["user"]
    editor_member = by_name["Editor"]["id"]
    author_member = by_name["Author"]["id"]

    editor_suspends = client.post(
        f"/api/v1/publications/{publication_id}/members/{author_member}/suspend",
        headers=_auth(editor_token),
    )
    assert editor_suspends.status_code == 403
    suspended = client.post(
        f"/api/v1/publications/{publication_id}/members/{author_member}/suspend",
        headers=_auth(owner),
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    denied = client.post(
        "/api/v1/posts",
        headers=_auth(author_token),
        json={"title": "Suspended Draft Title", "content": "Body", "publication_id": publication_id},
    )
    assert denied.status_code == 403
    owner_member = by_name["Owner"]["id"]
    cannot_suspend_owner = client.post(
        f"/api/v1/publications/{publication_id}/members/{owner_member}/suspend",
        headers=_auth(owner),
    )
    assert cannot_suspend_owner.status_code == 409

    client.post(
        f"/api/v1/publications/{publication_id}/members/{author_member}/remove",
        headers=_auth(owner),
    )
    transferred = client.post(
        f"/api/v1/publications/{publication_id}/transfer-ownership",
        headers=_auth(owner),
        json={"user_id": by_name["Editor"]["user"]["id"]},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["caller_role"] == "editor"
    old_owner_removes_new = client.post(
        f"/api/v1/publications/{publication_id}/members/{editor_member}/remove",
        headers=_auth(owner),
    )
    assert old_owner_removes_new.status_code == 403
    logs = client.get(
        f"/api/v1/publications/{publication_id}/audit-logs",
        headers=_auth(editor_token),
    )
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()["items"]}
    assert "ownership_transferred" in actions
    assert "token_hash" not in logs.text
    author_logs = client.get(
        f"/api/v1/publications/{publication_id}/audit-logs",
        headers=_auth(author_token),
    )
    assert author_logs.status_code == 403


def test_invitations_are_single_use_and_do_not_grant_platform_power(client: TestClient) -> None:
    owner = _verified_reader(client, "Host", "host.pub@example.com")
    publication = _create_publication(client, owner, slug="invite-desk", editors_can_invite=False)
    publication_id = str(publication["id"])
    owner_role = client.post(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(owner),
        json={"email": "guest.pub@example.com", "role": "owner"},
    )
    assert owner_role.status_code == 422

    guest = _verified_reader(client, "Guest", "guest.pub@example.com")
    created = _invite(client, owner, publication_id, "guest.pub@example.com", "contributor")
    assert created["email_delivery"] == "sent"
    assert "token_hash" not in created["invitation"]
    assert "#token=" not in str(created)
    duplicate = client.post(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(owner),
        json={"email": "Guest.Pub@example.com", "role": "author"},
    )
    assert duplicate.status_code == 409

    _register(client, "Wrong", "wrong.pub@example.com")
    _promote("wrong.pub@example.com", UserRole.READER)
    wrong = _login(client, "wrong.pub@example.com")
    raw = _token_for(client, "guest.pub@example.com")
    mismatch = _accept(client, wrong, raw)
    assert mismatch.status_code == 403

    _register(client, "Pending", "pending.pub@example.com")
    pending = _login(client, "pending.pub@example.com")
    _invite(client, owner, publication_id, "pending.pub@example.com", "author")
    unverified = _accept(client, pending, _token_for(client, "pending.pub@example.com"))
    assert unverified.status_code == 403
    assert unverified.json()["error"]["message"] == "Email verification is required."

    _expire("guest.pub@example.com")
    expired = _accept(client, guest, raw)
    assert expired.status_code == 409
    reused_expired = _accept(client, guest, raw)
    assert reused_expired.status_code == 409

    _invite(client, owner, publication_id, "guest.pub@example.com", "contributor")
    revoked_token = _token_for(client, "guest.pub@example.com")
    invitation_id = client.get(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(owner),
    ).json()["items"][0]["id"]
    revoked = client.post(
        f"/api/v1/publications/{publication_id}/invitations/{invitation_id}/revoke",
        headers=_auth(owner),
    )
    assert revoked.status_code == 200
    assert _accept(client, guest, revoked_token).status_code == 409

    _invite(client, owner, publication_id, "guest.pub@example.com", "contributor")
    accepted = _accept(client, guest, _token_for(client, "guest.pub@example.com"))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "contributor"
    assert _accept(client, guest, _token_for(client, "guest.pub@example.com")).status_code == 409
    profile = client.get("/api/v1/users/me", headers=_auth(guest))
    assert profile.json()["role"] == "reader"
    admin_list = client.get("/api/v1/posts/admin/all", headers=_auth(guest))
    assert admin_list.status_code == 403

    editor = _verified_reader(client, "DeskEd", "desked.pub@example.com")
    _invite(client, owner, publication_id, "desked.pub@example.com", "editor")
    assert _accept(client, editor, _token_for(client, "desked.pub@example.com")).status_code == 200
    editor_invite = client.post(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(editor),
        json={"email": "extra.pub@example.com", "role": "author"},
    )
    assert editor_invite.status_code == 403
    promoted = client.patch(
        f"/api/v1/publications/{publication_id}",
        headers=_auth(owner),
        json={"editors_can_invite": True},
    )
    assert promoted.status_code == 200
    editor_grants_editor = client.post(
        f"/api/v1/publications/{publication_id}/invitations",
        headers=_auth(editor),
        json={"email": "extra.pub@example.com", "role": "editor"},
    )
    assert editor_grants_editor.status_code == 403


def test_editorial_workflow_keeps_the_original_author(client: TestClient) -> None:
    owner = _verified_reader(client, "Chief", "chief.pub@example.com")
    publication = _create_publication(client, owner, slug="city-desk")
    publication_id = str(publication["id"])
    contributor = _verified_reader(client, "Cora", "cora.pub@example.com")
    editor = _verified_reader(client, "Eli", "eli.pub@example.com")
    _invite(client, owner, publication_id, "cora.pub@example.com", "contributor")
    _invite(client, owner, publication_id, "eli.pub@example.com", "editor")
    assert _accept(client, contributor, _token_for(client, "cora.pub@example.com")).status_code == 200
    assert _accept(client, editor, _token_for(client, "eli.pub@example.com")).status_code == 200

    independent = client.post(
        "/api/v1/posts",
        headers=_auth(contributor),
        json={"title": "Independent Note From Cora", "content": "Not in a publication."},
    )
    assert independent.status_code == 403

    created = client.post(
        "/api/v1/posts",
        headers=_auth(contributor),
        json={
            "title": "Dispatch From the Field",
            "content": "The first report from the field.",
            "publication_id": publication_id,
        },
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]
    assert created.json()["author"]["username"] == "Cora"
    assert created.json()["editorial_status"] == "draft"
    assert created.json()["publication_id"] == publication_id

    early_publish = client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(contributor))
    assert early_publish.status_code == 403
    early_approve = client.post(f"/api/v1/posts/{post_id}/approve", headers=_auth(contributor))
    assert early_approve.status_code == 403
    submitted = client.post(f"/api/v1/posts/{post_id}/submit", headers=_auth(contributor))
    assert submitted.status_code == 200
    assert submitted.json()["editorial_status"] == "submitted"
    locked = client.patch(
        f"/api/v1/posts/{post_id}",
        headers=_auth(contributor),
        json={"content": "A rewrite while the editors have it."},
    )
    assert locked.status_code == 403

    review = client.post(f"/api/v1/posts/{post_id}/start-review", headers=_auth(editor))
    assert review.status_code == 200
    assert review.json()["editorial_status"] == "in_review"
    changes = client.post(
        f"/api/v1/posts/{post_id}/request-changes",
        headers=_auth(editor),
        json={"reason": "Add the date of the interview."},
    )
    assert changes.status_code == 200
    assert changes.json()["editorial_status"] == "changes_requested"
    revised = client.patch(
        f"/api/v1/posts/{post_id}",
        headers=_auth(contributor),
        json={"content": "The interview took place on Monday."},
    )
    assert revised.status_code == 200
    resubmitted = client.post(f"/api/v1/posts/{post_id}/submit", headers=_auth(contributor))
    assert resubmitted.status_code == 200
    invalid = client.post(f"/api/v1/posts/{post_id}/approve", headers=_auth(contributor))
    assert invalid.status_code == 403
    approved = client.post(f"/api/v1/posts/{post_id}/approve", headers=_auth(editor))
    assert approved.status_code == 200
    assert approved.json()["editorial_status"] == "approved"
    assert approved.json()["author"]["username"] == "Cora"
    assert approved.json()["status"] == "draft"

    published = client.post(f"/api/v1/posts/{post_id}/publish", headers=_auth(editor))
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["author"]["username"] == "Cora"
    slug = published.json()["slug"]
    public = client.get(f"/api/v1/posts/{slug}")
    assert public.status_code == 200
    assert public.json()["author"]["username"] == "Cora"
    listed = client.get("/api/v1/publications/city-desk/posts")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = client.get(
        f"/api/v1/publications/{publication_id}/editorial/posts/{post_id}",
        headers=_auth(editor),
    )
    assert detail.status_code == 200
    event_actions = [item["action"] for item in detail.json()["events"]]
    assert event_actions == [
        "submit",
        "start_review",
        "request_changes",
        "submit",
        "approve",
        "publish",
    ]
    assert detail.json()["events"][2]["reason"] == "Add the date of the interview."
    submissions = client.get(
        f"/api/v1/publications/{publication_id}/editorial/submissions",
        headers=_auth(contributor),
    )
    assert submissions.status_code == 403

    outsider = _verified_reader(client, "OtherAuthor", "other.author@example.com")
    _promote("other.author@example.com", UserRole.AUTHOR)
    outsider = _login(client, "other.author@example.com")
    blocked = client.patch(
        f"/api/v1/posts/{post_id}",
        headers=_auth(outsider),
        json={"excerpt": "Not this author"},
    )
    assert blocked.status_code == 404

    direct = _create_publication(
        client, owner, name="Fast Desk", slug="fast-desk", requires_review=False
    )
    _invite(client, owner, str(direct["id"]), "cora.pub@example.com", "author")
    assert _accept(client, contributor, _token_for(client, "cora.pub@example.com")).status_code == 200
    quick = client.post(
        "/api/v1/posts",
        headers=_auth(contributor),
        json={
            "title": "A Note Without Review",
            "content": "Published by the author.",
            "publication_id": direct["id"],
        },
    )
    assert quick.status_code == 201
    direct_publish = client.post(
        f"/api/v1/posts/{quick.json()['id']}/publish",
        headers=_auth(contributor),
    )
    assert direct_publish.status_code == 200, direct_publish.text
    assert direct_publish.json()["author"]["username"] == "Cora"

    schema = client.get("/api/v1/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/publications" in schema.text
    assert "/api/v1/invitations/accept" in schema.text
