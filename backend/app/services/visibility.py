"""Whether a published article is visible to anonymous readers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.post import Post, PostStatus
from app.models.publication import Publication, PublicationStatus, PublicationVisibility


def is_publicly_listed(session: Session, post: Post | None) -> bool:
    """Published independent articles, and published articles of active public publications."""

    if post is None or post.deleted_at is not None or post.status is not PostStatus.PUBLISHED:
        return False
    if post.publication_id is None:
        return True
    publication = session.get(Publication, post.publication_id)
    if publication is None or publication.deleted_at is not None:
        return False
    return (
        publication.status is PublicationStatus.ACTIVE
        and publication.visibility is PublicationVisibility.PUBLIC
    )
