"""Revision history for article content."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.post_revision import PostRevision
from app.models.user import User
from app.repositories.post_revision_repository import PostRevisionRepository
from app.services.exceptions import NotFoundError


def record_previous_content(session: Session, post: Post, editor: User) -> PostRevision:
    """Store the current title, excerpt, and content before they change."""

    revisions = PostRevisionRepository(session)
    revision = PostRevision(
        post_id=post.id,
        edited_by=editor.id,
        title=post.title,
        excerpt=post.excerpt,
        content=post.content,
        revision_number=revisions.next_number(post.id),
    )
    return revisions.add(revision)


def list_revisions(session: Session, post_id: uuid.UUID) -> list[PostRevision]:
    """Return revisions in ascending revision number."""

    return PostRevisionRepository(session).list_for_post(post_id)


def get_revision(
    session: Session, post_id: uuid.UUID, revision_id: uuid.UUID
) -> PostRevision:
    """Return one revision or raise when it does not belong to the article."""

    revision = PostRevisionRepository(session).get(post_id, revision_id)
    if revision is None:
        raise NotFoundError("Revision not found.")
    return revision
