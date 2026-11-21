"""Tag persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models.post import Post, PostStatus
from app.models.tag import Tag, post_tags


class TagRepository:
    """Read and write tags without applying visibility rules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, tag: Tag) -> Tag:
        self.session.add(tag)
        self.session.flush()
        return tag

    def get(self, tag_id: uuid.UUID) -> Tag | None:
        return self.session.get(Tag, tag_id)

    def get_many(self, tag_ids: list[uuid.UUID]) -> list[Tag]:
        if not tag_ids:
            return []
        return list(self.session.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all())

    def get_by_slug(self, slug: str) -> Tag | None:
        return self.session.scalar(select(Tag).where(Tag.slug == slug))

    def get_by_name_key(self, name_key: str) -> Tag | None:
        return self.session.scalar(select(Tag).where(Tag.name_key == name_key))

    def slug_in_use(self, slug: str, *, excluding: uuid.UUID | None = None) -> bool:
        found = self.session.scalar(select(Tag.id).where(Tag.slug == slug))
        return found is not None and found != excluding

    def page_public(self, *, page: int, page_size: int) -> tuple[list[Tag], int]:
        visible = self._public_tag_ids()
        total = self.session.scalar(select(func.count(Tag.id)).where(Tag.id.in_(visible)))
        rows = self.session.scalars(
            select(Tag)
            .where(Tag.id.in_(visible))
            .order_by(Tag.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)

    def page_all(self, *, page: int, page_size: int) -> tuple[list[Tag], int]:
        total = self.session.scalar(select(func.count(Tag.id)))
        rows = self.session.scalars(
            select(Tag)
            .order_by(Tag.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)

    def is_public(self, tag_id: uuid.UUID) -> bool:
        statement = self._public_tag_ids().where(post_tags.c.tag_id == tag_id)
        return self.session.scalar(select(exists(statement))) is True

    def delete(self, tag: Tag) -> None:
        self.session.delete(tag)
        self.session.flush()

    def _public_tag_ids(self):
        return (
            select(post_tags.c.tag_id)
            .join(Post, Post.id == post_tags.c.post_id)
            .where(Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
        )
