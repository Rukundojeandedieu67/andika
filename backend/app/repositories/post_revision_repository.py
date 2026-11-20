"""Article revision persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.post_revision import PostRevision


class PostRevisionRepository:
    """Read and append article revisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, revision: PostRevision) -> PostRevision:
        self.session.add(revision)
        self.session.flush()
        return revision

    def next_number(self, post_id: uuid.UUID) -> int:
        current = self.session.scalar(
            select(func.max(PostRevision.revision_number)).where(
                PostRevision.post_id == post_id
            )
        )
        return int(current or 0) + 1

    def list_for_post(self, post_id: uuid.UUID) -> list[PostRevision]:
        return list(
            self.session.scalars(
                select(PostRevision)
                .where(PostRevision.post_id == post_id)
                .order_by(PostRevision.revision_number.asc())
            ).all()
        )

    def get(self, post_id: uuid.UUID, revision_id: uuid.UUID) -> PostRevision | None:
        return self.session.scalar(
            select(PostRevision).where(
                PostRevision.post_id == post_id,
                PostRevision.id == revision_id,
            )
        )
