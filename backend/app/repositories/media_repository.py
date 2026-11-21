"""Media persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.media import Media, MediaStatus


class MediaRepository:
    """Read and write media records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, media: Media) -> Media:
        self.session.add(media)
        self.session.flush()
        return media

    def get(self, media_id: uuid.UUID) -> Media | None:
        return self.session.scalar(
            select(Media)
            .options(selectinload(Media.variants))
            .where(Media.id == media_id)
        )

    def get_active_by_checksum(self, owner_id: uuid.UUID, checksum: str) -> Media | None:
        return self.session.scalar(
            select(Media)
            .options(selectinload(Media.variants))
            .where(
                Media.owner_id == owner_id,
                Media.checksum == checksum,
                Media.deleted_at.is_(None),
            )
        )

    def page_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        mime_type: str | None,
    ) -> tuple[list[Media], int]:
        clauses = [Media.owner_id == owner_id, Media.deleted_at.is_(None)]
        clauses.extend(self._filters(search=search, mime_type=mime_type, status=None))
        return self._page(clauses, page=page, page_size=page_size)

    def page_all(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        mime_type: str | None,
        owner_id: uuid.UUID | None,
        status: MediaStatus | None,
    ) -> tuple[list[Media], int]:
        clauses: list[ColumnElement[bool]] = [Media.deleted_at.is_(None)]
        if owner_id is not None:
            clauses.append(Media.owner_id == owner_id)
        clauses.extend(self._filters(search=search, mime_type=mime_type, status=status))
        return self._page(clauses, page=page, page_size=page_size)

    def _filters(
        self,
        *,
        search: str | None,
        mime_type: str | None,
        status: MediaStatus | None,
    ) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = []
        if mime_type is not None:
            clauses.append(Media.mime_type == mime_type)
        if status is not None:
            clauses.append(Media.status == status)
        if search:
            term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{term}%"
            clauses.append(
                or_(
                    Media.original_filename.ilike(pattern, escape="\\"),
                    Media.title.ilike(pattern, escape="\\"),
                )
            )
        return clauses

    def _page(
        self, clauses: list[ColumnElement[bool]], *, page: int, page_size: int
    ) -> tuple[list[Media], int]:
        total = self.session.scalar(select(func.count(Media.id)).where(*clauses))
        rows = self.session.scalars(
            select(Media)
            .options(selectinload(Media.variants))
            .where(*clauses)
            .order_by(Media.created_at.desc(), Media.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)
