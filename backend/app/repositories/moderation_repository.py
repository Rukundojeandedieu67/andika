"""Moderation history persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.models.moderation_log import ModerationLog


class ModerationRepository:
    """Append and read moderation logs. Logs are not updated or deleted here."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entry: ModerationLog) -> ModerationLog:
        self.session.add(entry)
        self.session.flush()
        return entry

    def page(
        self,
        *,
        page: int,
        page_size: int,
        comment_id: uuid.UUID | None,
        moderator_id: uuid.UUID | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[list[ModerationLog], int]:
        clauses: list[ColumnElement[bool]] = []
        if comment_id is not None:
            clauses.append(ModerationLog.comment_id == comment_id)
        if moderator_id is not None:
            clauses.append(ModerationLog.moderator_id == moderator_id)
        if created_from is not None:
            clauses.append(ModerationLog.created_at >= created_from)
        if created_to is not None:
            clauses.append(ModerationLog.created_at <= created_to)
        total = self.session.scalar(select(func.count(ModerationLog.id)).where(*clauses))
        rows = self.session.scalars(
            select(ModerationLog)
            .where(*clauses)
            .order_by(ModerationLog.created_at.desc(), ModerationLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)
