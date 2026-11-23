"""Comment creation, threading, and ownership.

Verified accounts are approved immediately. Unverified accounts stay pending
until an article author or an administrator approves them. Rejected comments
are never shown publicly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.comment import Comment, CommentStatus
from app.models.post import Post, PostStatus
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.schemas.comment import CommentRead
from app.services.exceptions import ConflictError, NotFoundError, ServiceError

REMOVED_BODY = "This comment was removed."


def create_comment(
    session: Session,
    *,
    post_id: uuid.UUID,
    author: User,
    body: str,
    parent_id: uuid.UUID | None = None,
) -> Comment:
    """Add a root comment or a reply on a published article that allows discussion."""

    post = _open_post(session, post_id)
    parent = _reply_parent(session, post, parent_id)
    comments = CommentRepository(session)
    if comments.find_duplicate(
        post_id=post.id,
        author_id=author.id,
        parent_id=parent.id if parent is not None else None,
        body=body,
    ):
        raise ConflictError("You already posted that comment.")
    comment = Comment(
        post_id=post.id,
        author_id=author.id,
        parent_id=parent.id if parent is not None else None,
        body=body,
        status=CommentStatus.APPROVED if author.is_verified else CommentStatus.PENDING,
        author=author,
    )
    return comments.add(comment)


def update_comment(
    session: Session, comment_id: uuid.UUID, actor: User, body: str
) -> Comment:
    """Replace the body of a comment owned by the caller."""

    comment = _owned(session, comment_id, actor)
    if comment.body == body:
        return comment
    duplicate = CommentRepository(session).find_duplicate(
        post_id=comment.post_id,
        author_id=actor.id,
        parent_id=comment.parent_id,
        body=body,
    )
    if duplicate is not None and duplicate.id != comment.id:
        raise ConflictError("You already posted that comment.")
    now = datetime.now(UTC)
    comment.body = body
    comment.edited_at = now
    comment.updated_at = now
    session.flush()
    return comment


def delete_comment(session: Session, comment_id: uuid.UUID, actor: User) -> None:
    """Hide a comment body without removing its author or its replies."""

    comment = _owned(session, comment_id, actor)
    now = datetime.now(UTC)
    comment.deleted_at = now
    comment.updated_at = now
    session.flush()


def list_public(
    session: Session, post_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[CommentRead], int]:
    """Return approved threads for a published article."""

    _published_post(session, post_id)
    comments = CommentRepository(session)
    roots, total = comments.page_public_roots(post_id, page=page, page_size=page_size)
    replies = comments.public_replies([root.id for root in roots])
    grouped: dict[uuid.UUID, list[Comment]] = {}
    for reply in replies:
        if reply.parent_id is not None:
            grouped.setdefault(reply.parent_id, []).append(reply)
    return (
        [_public(root, grouped.get(root.id, [])) for root in roots],
        total,
    )


def list_mine(
    session: Session, actor: User, *, page: int, page_size: int
) -> tuple[list[Comment], int]:
    """Return the caller's comments that have not been deleted."""

    return CommentRepository(session).page_for_author(
        actor.id, page=page, page_size=page_size
    )


def _open_post(session: Session, post_id: uuid.UUID) -> Post:
    post = _published_post(session, post_id)
    if not post.allow_comments:
        raise ServiceError("Comments are closed on this article.", 403)
    return post


def _published_post(session: Session, post_id: uuid.UUID) -> Post:
    post = session.get(Post, post_id)
    if post is None or post.deleted_at is not None or post.status is not PostStatus.PUBLISHED:
        raise NotFoundError()
    return post


def _reply_parent(session: Session, post: Post, parent_id: uuid.UUID | None) -> Comment | None:
    if parent_id is None:
        return None
    parent = CommentRepository(session).get(parent_id)
    if parent is None or parent.post_id != post.id:
        raise NotFoundError("Comment not found.")
    if parent.parent_id is not None:
        raise ConflictError("Replies cannot contain replies.")
    if parent.deleted_at is not None or parent.status is not CommentStatus.APPROVED:
        raise ConflictError("That comment is not open for replies.")
    return parent


def _owned(session: Session, comment_id: uuid.UUID, actor: User) -> Comment:
    comment = CommentRepository(session).get(comment_id)
    if comment is None or comment.deleted_at is not None or comment.author_id != actor.id:
        raise NotFoundError("Comment not found.")
    return comment


def _public(comment: Comment, replies: list[Comment]) -> CommentRead:
    removed = comment.deleted_at is not None
    return CommentRead(
        id=comment.id,
        body=REMOVED_BODY if removed else comment.body,
        created_at=comment.created_at,
        edited_at=None if removed else comment.edited_at,
        author=comment.author,
        replies=[_public(reply, []) for reply in replies],
    )
