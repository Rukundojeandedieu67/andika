"""Turn completed business events into notifications. Callers stay inside one transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.editorial import EditorialEvent
from app.models.notification import NotificationType
from app.models.post import Post
from app.models.publication import (
    MembershipRole,
    MembershipStatus,
    Publication,
    PublicationMembership,
)
from app.models.user import User
from app.services.notification_service import emit

_EDITOR_ROLES = (MembershipRole.OWNER, MembershipRole.EDITOR)


def comment_created(
    session: Session,
    post: Post,
    *,
    comment_id: uuid.UUID,
    actor: User,
    parent_author_id: uuid.UUID | None,
) -> None:
    """Tell the article author about a comment, and the parent author about a reply."""

    name = _person(actor)
    title = _short(post.title)
    if parent_author_id is not None and parent_author_id != actor.id:
        emit(
            session,
            recipient_id=parent_author_id,
            actor=actor,
            kind=NotificationType.COMMENT_REPLY_RECEIVED,
            title="New reply",
            message=f"{name} replied to your comment on {title}.",
            resource_type="post",
            resource_id=post.id,
            action_url=f"/api/v1/posts/{post.slug}",
            details={"article_slug": post.slug},
            idempotency_key=f"comment:{comment_id}:reply",
        )
    if post.author_id == actor.id or post.author_id == parent_author_id:
        return
    emit(
        session,
        recipient_id=post.author_id,
        actor=actor,
        kind=NotificationType.COMMENT_RECEIVED,
        title="New comment",
        message=f"{name} commented on {title}.",
        resource_type="post",
        resource_id=post.id,
        action_url=f"/api/v1/posts/{post.slug}",
        details={"article_slug": post.slug},
        idempotency_key=f"comment:{comment_id}:received",
    )


def comment_moderated(
    session: Session,
    *,
    comment_author_id: uuid.UUID,
    actor: User,
    post_id: uuid.UUID,
    status_value: str,
    log_id: uuid.UUID,
) -> None:
    """Tell the comment author about a moderation decision, without the comment text."""

    kind = {
        "approved": NotificationType.COMMENT_APPROVED,
        "hidden": NotificationType.COMMENT_HIDDEN,
        "rejected": NotificationType.COMMENT_REJECTED,
    }.get(status_value)
    if kind is None:
        return
    post = session.get(Post, post_id)
    article = _short(post.title) if post is not None else "an article"
    slug = None if post is None else post.slug
    emit(
        session,
        recipient_id=comment_author_id,
        actor=actor,
        kind=kind,
        title="Comment moderation",
        message=f"Your comment on {article} was {status_value}.",
        resource_type="post",
        resource_id=post_id,
        action_url=None if slug is None else f"/api/v1/posts/{slug}",
        details={"status": status_value},
        idempotency_key=f"moderation:{log_id}",
    )


def editorial_event(
    session: Session,
    post: Post,
    actor: User,
    action: str,
    event: EditorialEvent,
    reason: str | None,
) -> None:
    """Notify editors of a submission, and the author of later review decisions."""

    if post.publication_id is None:
        return
    publication = session.get(Publication, post.publication_id)
    if publication is None:
        return
    title = _short(post.title)
    path = f"/api/v1/publications/{publication.id}/editorial/posts/{post.id}"
    if action == "submit":
        for recipient_id in _editor_ids(session, publication.id):
            emit(
                session,
                recipient_id=recipient_id,
                actor=actor,
                kind=NotificationType.ARTICLE_SUBMITTED_FOR_REVIEW,
                title="Article submitted",
                message=f"{_person(actor)} submitted {title} to {publication.name}.",
                resource_type="post",
                resource_id=post.id,
                action_url=path,
                details={"publication_slug": publication.slug},
                idempotency_key=f"editorial:{event.id}:{recipient_id}",
            )
        return
    author_events = {
        "start_review": (
            NotificationType.ARTICLE_REVIEW_STARTED,
            f"Review started on {title}.",
        ),
        "request_changes": (
            NotificationType.ARTICLE_CHANGES_REQUESTED,
            _changes_message(title, reason),
        ),
        "approve": (NotificationType.ARTICLE_APPROVED, f"{title} was approved."),
        "publish": (NotificationType.ARTICLE_PUBLISHED, f"{title} was published."),
        "unpublish": (NotificationType.ARTICLE_UNPUBLISHED, f"{title} was unpublished."),
    }
    chosen = author_events.get(action)
    if chosen is None:
        return
    kind, message = chosen
    emit(
        session,
        recipient_id=post.author_id,
        actor=actor,
        kind=kind,
        title="Editorial update",
        message=message,
        resource_type="post",
        resource_id=post.id,
        action_url=path,
        details={"publication_slug": publication.slug},
        idempotency_key=f"editorial:{event.id}",
    )


def invitation_received(
    session: Session,
    *,
    recipient_id: uuid.UUID,
    actor: User,
    publication: Publication,
    invitation_id: uuid.UUID,
) -> None:
    emit(
        session,
        recipient_id=recipient_id,
        actor=actor,
        kind=NotificationType.PUBLICATION_INVITATION_RECEIVED,
        title="Publication invitation",
        message=f"{_person(actor)} invited you to {publication.name}.",
        resource_type="publication",
        resource_id=publication.id,
        action_url=None,
        details={"publication_name": publication.name},
        idempotency_key=f"invitation:{invitation_id}:received",
    )


def invitation_accepted(
    session: Session, *, actor: User, publication: Publication, invitation_id: uuid.UUID
) -> None:
    for recipient_id in _editor_ids(session, publication.id):
        emit(
            session,
            recipient_id=recipient_id,
            actor=actor,
            kind=NotificationType.PUBLICATION_INVITATION_ACCEPTED,
            title="Invitation accepted",
            message=f"{_person(actor)} joined {publication.name}.",
            resource_type="publication",
            resource_id=publication.id,
            action_url=f"/api/v1/publications/{publication.id}/members",
            details={"publication_slug": publication.slug},
            idempotency_key=f"invitation:{invitation_id}:accepted:{recipient_id}",
        )


def membership_changed(
    session: Session,
    *,
    publication: Publication,
    actor: User,
    recipient_id: uuid.UUID,
    kind: NotificationType,
    message: str,
    audit_id: uuid.UUID,
) -> None:
    emit(
        session,
        recipient_id=recipient_id,
        actor=actor,
        kind=kind,
        title="Publication membership",
        message=message,
        resource_type="publication",
        resource_id=publication.id,
        action_url=None,
        details={"publication_name": publication.name},
        idempotency_key=f"audit:{audit_id}",
    )


def _editor_ids(session: Session, publication_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(PublicationMembership.user_id).where(
                PublicationMembership.publication_id == publication_id,
                PublicationMembership.status == MembershipStatus.ACTIVE,
                PublicationMembership.role.in_(_EDITOR_ROLES),
            )
        ).all()
    )


def _changes_message(title: str, reason: str | None) -> str:
    if reason:
        return f"Changes were requested on {title}. {_short(reason)}"
    return f"Changes were requested on {title}."


def _person(user: User) -> str:
    return user.full_name or user.username


def _short(value: str) -> str:
    return " ".join(value.split())[:120]
