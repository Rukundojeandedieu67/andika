"""Category persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    """Read and write categories without applying visibility rules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, category: Category) -> Category:
        self.session.add(category)
        self.session.flush()
        return category

    def get(self, category_id: uuid.UUID) -> Category | None:
        return self.session.get(Category, category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        return self.session.scalar(select(Category).where(Category.slug == slug))

    def get_by_name_key(self, name_key: str) -> Category | None:
        return self.session.scalar(select(Category).where(Category.name_key == name_key))

    def slug_in_use(self, slug: str, *, excluding: uuid.UUID | None = None) -> bool:
        found = self.session.scalar(select(Category.id).where(Category.slug == slug))
        return found is not None and found != excluding

    def list_all(self) -> list[Category]:
        return list(
            self.session.scalars(select(Category).order_by(Category.name.asc())).all()
        )

    def list_children(self, parent_id: uuid.UUID) -> list[Category]:
        return list(
            self.session.scalars(
                select(Category)
                .where(Category.parent_id == parent_id)
                .order_by(Category.name.asc())
            ).all()
        )

    def page(self, *, page: int, page_size: int) -> tuple[list[Category], int]:
        total = self.session.scalar(select(func.count(Category.id)))
        rows = self.session.scalars(
            select(Category)
            .order_by(Category.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)

    def delete(self, category: Category) -> None:
        self.session.delete(category)
        self.session.flush()
