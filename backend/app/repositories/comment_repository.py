"""Comment persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload

from app.models.comment import Comment, CommentStatus


class CommentRepository:
    """Read and write comments without applying visibility policy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, comment: Comment) -> Comment:
        self.session.add(comment)
        self.session.flush()
        return comment

    def get(self, comment_id: uuid.UUID, *, lock: bool = False) -> Comment | None:
        statement = select(Comment).where(Comment.id == comment_id)
        if lock and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        else:
            statement = statement.options(joinedload(Comment.author))
        return self.session.scalar(statement)

    def find_duplicate(
        self,
        *,
        post_id: uuid.UUID,
        author_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        body: str,
    ) -> Comment | None:
        parent = (
            Comment.parent_id.is_(None)
            if parent_id is None
            else Comment.parent_id == parent_id
        )
        return self.session.scalar(
            select(Comment).where(
                Comment.post_id == post_id,
                Comment.author_id == author_id,
                parent,
                Comment.body == body,
                Comment.deleted_at.is_(None),
            )
        )

    def page_public_roots(
        self, post_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[Comment], int]:
        reply = aliased(Comment)
        has_public_reply = (
            select(reply.id)
            .where(
                reply.parent_id == Comment.id,
                reply.deleted_at.is_(None),
                reply.status == CommentStatus.APPROVED,
            )
            .exists()
        )
        clauses = [
            Comment.post_id == post_id,
            Comment.parent_id.is_(None),
            or_(
                and_(
                    Comment.deleted_at.is_(None),
                    Comment.status == CommentStatus.APPROVED,
                ),
                and_(Comment.deleted_at.is_not(None), has_public_reply),
            ),
        ]
        return self._page(clauses, page=page, page_size=page_size, descending=False)

    def public_replies(self, root_ids: list[uuid.UUID]) -> list[Comment]:
        if not root_ids:
            return []
        rows = self.session.scalars(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(
                Comment.parent_id.in_(root_ids),
                Comment.deleted_at.is_(None),
                Comment.status == CommentStatus.APPROVED,
            )
            .order_by(Comment.created_at.asc(), Comment.id.asc())
        ).all()
        return list(rows)

    def page_for_author(
        self, author_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[Comment], int]:
        clauses = [Comment.author_id == author_id, Comment.deleted_at.is_(None)]
        return self._page(clauses, page=page, page_size=page_size, descending=True)

    def page_for_moderation(
        self,
        *,
        page: int,
        page_size: int,
        post_id: uuid.UUID | None,
        author_id: uuid.UUID | None,
        status: CommentStatus | None,
        search: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[list[Comment], int]:
        clauses: list[ColumnElement[bool]] = []
        if post_id is not None:
            clauses.append(Comment.post_id == post_id)
        if author_id is not None:
            clauses.append(Comment.author_id == author_id)
        if status is not None:
            clauses.append(Comment.status == status)
        if created_from is not None:
            clauses.append(Comment.created_at >= created_from)
        if created_to is not None:
            clauses.append(Comment.created_at <= created_to)
        if search:
            term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append(Comment.body.ilike(f"%{term}%", escape="\\"))
        return self._page(clauses, page=page, page_size=page_size, descending=True)

    def _page(
        self,
        clauses: list[ColumnElement[bool]],
        *,
        page: int,
        page_size: int,
        descending: bool,
    ) -> tuple[list[Comment], int]:
        total = self.session.scalar(select(func.count(Comment.id)).where(*clauses))
        order = Comment.created_at.desc() if descending else Comment.created_at.asc()
        identity = Comment.id.desc() if descending else Comment.id.asc()
        rows = self.session.scalars(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(*clauses)
            .order_by(order, identity)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)
