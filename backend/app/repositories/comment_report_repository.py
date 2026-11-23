"""Comment report persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.comment import Comment
from app.models.comment_report import CommentReport, ReportStatus


class CommentReportRepository:
    """Read and write comment reports."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, report: CommentReport) -> CommentReport:
        self.session.add(report)
        self.session.flush()
        return report

    def get(self, report_id: uuid.UUID) -> CommentReport | None:
        return self.session.scalar(
            select(CommentReport)
            .options(joinedload(CommentReport.reporter), joinedload(CommentReport.comment))
            .where(CommentReport.id == report_id)
        )

    def find_existing(self, comment_id: uuid.UUID, reporter_id: uuid.UUID) -> CommentReport | None:
        return self.session.scalar(
            select(CommentReport).where(
                CommentReport.comment_id == comment_id,
                CommentReport.reporter_id == reporter_id,
            )
        )

    def page(
        self,
        *,
        page: int,
        page_size: int,
        status: ReportStatus | None,
        post_id: uuid.UUID | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[list[CommentReport], int]:
        clauses: list[ColumnElement[bool]] = []
        if status is not None:
            clauses.append(CommentReport.status == status)
        if post_id is not None:
            clauses.append(
                CommentReport.comment_id.in_(
                    select(Comment.id).where(Comment.post_id == post_id)
                )
            )
        if created_from is not None:
            clauses.append(CommentReport.created_at >= created_from)
        if created_to is not None:
            clauses.append(CommentReport.created_at <= created_to)
        total = self.session.scalar(select(func.count(CommentReport.id)).where(*clauses))
        rows = self.session.scalars(
            select(CommentReport)
            .options(joinedload(CommentReport.reporter))
            .where(*clauses)
            .order_by(CommentReport.created_at.desc(), CommentReport.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total or 0)
