"""Author, publication, and administrator analytics."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import AdminUser, DatabaseSession, VerifiedUser
from app.schemas.analytics import (
    AdminContent,
    AdminOverview,
    AdminTimeSeries,
    ArticlePerformancePage,
    AuthorContributionPage,
    AuthorOverview,
    PublicationArticlePage,
    PublicationOverview,
    TimeSeries,
)
from app.schemas.common import ErrorResponse
from app.services import analytics_service
from app.services.analytics_service import ReportWindow, csv_cell
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}
Sort = Literal["views", "comments", "published_at"]
Period = Literal["day", "week", "month"]


class WindowQuery:
    """Shared date, period, and comparison arguments."""

    def __init__(
        self,
        date_from: Annotated[datetime | None, Query()] = None,
        date_to: Annotated[datetime | None, Query()] = None,
        period: Annotated[Period, Query()] = "day",
        compare: Annotated[bool, Query()] = False,
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        self.period = period
        self.compare = compare


WindowDep = Annotated[WindowQuery, Depends()]


def _raise(exc: ServiceError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _window(query: WindowQuery) -> ReportWindow:
    try:
        return analytics_service.parse_window(
            query.date_from, query.date_to, query.period, query.compare
        )
    except ServiceError as exc:
        _raise(exc)


def _csv(rows: list[list[object]], filename: str, truncated: bool) -> StreamingResponse:
    def chunks() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in rows:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow([csv_cell(cell) for cell in row])
            yield buffer.getvalue()

    return StreamingResponse(
        chunks(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Andika-Export-Limit": str(analytics_service.EXPORT_ROW_LIMIT),
            "X-Andika-Export-Truncated": "true" if truncated else "false",
        },
    )


@router.get(
    "/author/overview",
    response_model=AuthorOverview,
    summary="Analytics for the authenticated author's articles",
    responses=_ERRORS,
)
def author_overview(
    actor: VerifiedUser, session: DatabaseSession, query: WindowDep
) -> AuthorOverview:
    return analytics_service.author_overview(session, actor, _window(query))


@router.get(
    "/author/articles",
    response_model=ArticlePerformancePage,
    summary="Per-article analytics for the authenticated author",
    responses=_ERRORS,
)
def author_articles(
    actor: VerifiedUser,
    session: DatabaseSession,
    query: WindowDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[Sort, Query()] = "published_at",
) -> ArticlePerformancePage:
    return analytics_service.author_articles(
        session, actor, _window(query), page=page, page_size=page_size, sort=sort
    )


@router.get(
    "/author/timeseries",
    response_model=TimeSeries,
    summary="Author views, comments, and published articles over time",
    responses=_ERRORS,
)
def author_timeseries(
    actor: VerifiedUser, session: DatabaseSession, query: WindowDep
) -> TimeSeries:
    return analytics_service.author_timeseries(session, actor, _window(query))


@router.get(
    "/author/export",
    summary="CSV of the authenticated author's article analytics",
    responses=_ERRORS,
)
def author_export(
    actor: VerifiedUser,
    session: DatabaseSession,
    query: WindowDep,
    sort: Annotated[Sort, Query()] = "published_at",
) -> StreamingResponse:
    rows, truncated = analytics_service.author_export_rows(session, actor, _window(query), sort)
    return _csv(rows, "andika-author-analytics.csv", truncated)


@router.get(
    "/publications/{publication_id}/overview",
    response_model=PublicationOverview,
    summary="Analytics for one publication",
    responses=_ERRORS,
)
def publication_overview(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    query: WindowDep,
) -> PublicationOverview:
    try:
        return analytics_service.publication_overview(
            session, publication_id, actor, _window(query)
        )
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/publications/{publication_id}/articles",
    response_model=PublicationArticlePage,
    summary="Article analytics inside one publication",
    responses=_ERRORS,
)
def publication_articles(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    query: WindowDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[Sort, Query()] = "published_at",
) -> PublicationArticlePage:
    try:
        return analytics_service.publication_articles(
            session,
            publication_id,
            actor,
            _window(query),
            page=page,
            page_size=page_size,
            sort=sort,
        )
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/publications/{publication_id}/authors",
    response_model=AuthorContributionPage,
    summary="Author contributions inside one publication",
    responses=_ERRORS,
)
def publication_authors(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    query: WindowDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuthorContributionPage:
    try:
        return analytics_service.publication_authors(
            session,
            publication_id,
            actor,
            _window(query),
            page=page,
            page_size=page_size,
        )
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/publications/{publication_id}/export",
    summary="CSV of one publication's article analytics",
    responses=_ERRORS,
)
def publication_export(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    query: WindowDep,
    sort: Annotated[Sort, Query()] = "published_at",
) -> StreamingResponse:
    try:
        rows, truncated = analytics_service.publication_export_rows(
            session, publication_id, actor, _window(query), sort
        )
    except ServiceError as exc:
        _raise(exc)
    return _csv(rows, "andika-publication-analytics.csv", truncated)


@router.get(
    "/admin/overview",
    response_model=AdminOverview,
    summary="Platform analytics for an administrator",
    responses=_ERRORS,
)
def admin_overview(
    _admin: AdminUser, session: DatabaseSession, query: WindowDep
) -> AdminOverview:
    return analytics_service.admin_overview(session, _window(query))


@router.get(
    "/admin/timeseries",
    response_model=AdminTimeSeries,
    summary="Platform activity over time",
    responses=_ERRORS,
)
def admin_timeseries(
    _admin: AdminUser, session: DatabaseSession, query: WindowDep
) -> AdminTimeSeries:
    return analytics_service.admin_timeseries(session, _window(query))


@router.get(
    "/admin/content",
    response_model=AdminContent,
    summary="Aggregated content performance",
    responses=_ERRORS,
)
def admin_content(
    _admin: AdminUser, session: DatabaseSession, query: WindowDep
) -> AdminContent:
    return analytics_service.admin_content(session, _window(query))


@router.get(
    "/admin/export",
    summary="CSV of aggregated platform content analytics",
    responses=_ERRORS,
)
def admin_export(
    _admin: AdminUser, session: DatabaseSession, query: WindowDep
) -> StreamingResponse:
    rows, truncated = analytics_service.admin_export_rows(session, _window(query))
    return _csv(rows, "andika-admin-analytics.csv", truncated)
