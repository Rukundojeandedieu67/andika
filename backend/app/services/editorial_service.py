"""Editorial workflow for publication articles. Independent articles do not use it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.editorial import EditorialEvent, EditorialStatus
from app.models.post import Post, PostStatus
from app.models.publication import MembershipRole, Publication
from app.models.user import User
from app.repositories.post_repository import PostRepository
from app.repositories.publication_repository import EditorialEventRepository
from app.schemas.post import PostListParams
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.publication_access import (
    EDITOR_ROLES,
    require_active_member,
    require_active_publication,
    require_editor,
    require_publication,
)

_SUBMIT_FROM = {EditorialStatus.DRAFT, EditorialStatus.CHANGES_REQUESTED}
_CHANGES_FROM = {EditorialStatus.SUBMITTED, EditorialStatus.IN_REVIEW}
_APPROVE_FROM = {EditorialStatus.SUBMITTED, EditorialStatus.IN_REVIEW}


def list_posts(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    params: PostListParams,
) -> tuple[list[Post], int]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    author_id = None if membership.role in EDITOR_ROLES else actor.id
    return PostRepository(session).list_editorial(
        publication.id, params, author_id=author_id, statuses=None
    )


def list_submissions(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    params: PostListParams,
) -> tuple[list[Post], int]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    require_editor(membership)
    return PostRepository(session).list_editorial(
        publication.id,
        params,
        author_id=None,
        statuses=[EditorialStatus.SUBMITTED, EditorialStatus.IN_REVIEW],
    )


def get_post(
    session: Session, publication_id: uuid.UUID, post_id: uuid.UUID, actor: User
) -> tuple[Post, list[EditorialEvent]]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    post = _publication_post(session, post_id, publication)
    if membership.role not in EDITOR_ROLES and post.author_id != actor.id:
        raise NotFoundError()
    return post, EditorialEventRepository(session).for_post(post.id)


def submit_post(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    post = PostRepository(session).get(post_id, lock=True)
    publication = _require_article_publication(session, post)
    membership = require_active_member(session, publication, actor)
    if post.author_id != actor.id:
        raise ServiceError("You can only submit your own article.", 403)
    if membership.role not in {
        MembershipRole.OWNER,
        MembershipRole.EDITOR,
        MembershipRole.AUTHOR,
        MembershipRole.CONTRIBUTOR,
    }:
        raise ServiceError("You do not have permission to perform this action.", 403)
    if post.status is not PostStatus.DRAFT:
        raise ConflictError("Only a draft can be submitted.")
    if post.editorial_status not in _SUBMIT_FROM:
        raise ConflictError("That editorial transition is not allowed.")
    _move(session, post, actor, "submit", EditorialStatus.SUBMITTED, reason=None)
    return post


def start_review(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    post, _publication = _editor_post(session, post_id, actor)
    if post.editorial_status is not EditorialStatus.SUBMITTED:
        raise ConflictError("That editorial transition is not allowed.")
    _move(session, post, actor, "start_review", EditorialStatus.IN_REVIEW, reason=None)
    return post


def request_changes(
    session: Session, post_id: uuid.UUID, actor: User, reason: str
) -> Post:
    cleaned = " ".join(reason.split())
    if cleaned == "":
        raise ServiceError("Explain what needs to change.", 422)
    post, _publication = _editor_post(session, post_id, actor)
    if post.editorial_status not in _CHANGES_FROM:
        raise ConflictError("That editorial transition is not allowed.")
    _move(
        session,
        post,
        actor,
        "request_changes",
        EditorialStatus.CHANGES_REQUESTED,
        reason=cleaned,
    )
    return post


def approve_post(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    post, _publication = _editor_post(session, post_id, actor)
    if post.editorial_status not in _APPROVE_FROM:
        raise ConflictError("That editorial transition is not allowed.")
    _move(session, post, actor, "approve", EditorialStatus.APPROVED, reason=None)
    return post


def record_transition(
    session: Session,
    *,
    post: Post,
    actor: User,
    action: str,
    from_status: EditorialStatus | None,
    to_status: EditorialStatus,
    reason: str | None = None,
) -> EditorialEvent:
    """Store one editorial transition in the same transaction as the article change."""

    event = EditorialEventRepository(session).add(
        EditorialEvent(
            post_id=post.id,
            actor_id=actor.id,
            action=action,
            from_status=None if from_status is None else from_status.value,
            to_status=to_status.value,
            reason=reason,
        )
    )
    from app.services.notification_events import editorial_event

    editorial_event(session, post, actor, action, event, reason)
    return event


def _editor_post(session: Session, post_id: uuid.UUID, actor: User) -> tuple[Post, Publication]:
    post = PostRepository(session).get(post_id, lock=True)
    publication = _require_article_publication(session, post)
    membership = require_active_member(session, publication, actor)
    require_editor(membership)
    return post, publication


def _require_article_publication(session: Session, post: Post | None) -> Publication:
    if post is None or post.deleted_at is not None:
        raise NotFoundError()
    if post.publication_id is None or post.editorial_status is None:
        raise ConflictError("That article is not part of a publication.")
    publication = require_publication(session, post.publication_id, lock=True)
    require_active_publication(publication)
    return publication


def _publication_post(session: Session, post_id: uuid.UUID, publication: Publication) -> Post:
    post = PostRepository(session).get(post_id)
    if (
        post is None
        or post.deleted_at is not None
        or post.publication_id != publication.id
    ):
        raise NotFoundError()
    return post


def _move(
    session: Session,
    post: Post,
    actor: User,
    action: str,
    to_status: EditorialStatus,
    *,
    reason: str | None,
) -> None:
    previous = post.editorial_status
    post.editorial_status = to_status
    post.updated_at = datetime.now(UTC)
    record_transition(
        session,
        post=post,
        actor=actor,
        action=action,
        from_status=previous,
        to_status=to_status,
        reason=reason,
    )
    session.flush()
