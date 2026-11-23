"""Public search, suggestions, and discovery routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.dependencies import AdminUser, DatabaseSession, SettingsDep
from app.schemas.common import ErrorResponse
from app.schemas.search import (
    ArticleCardPage,
    ArticleFeed,
    ArticleSort,
    AuthorCardPage,
    PublicationCardPage,
    SearchResponse,
    SearchStats,
    SearchType,
    SuggestionList,
)
from app.services import search_service
from app.services.exceptions import ServiceError

router = APIRouter()
discovery_router = APIRouter()

_ERRORS = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/suggestions", response_model=SuggestionList, summary="Search suggestions")
def suggest(
    request: Request,
    session: DatabaseSession,
    settings: SettingsDep,
    q: Annotated[str, Query(max_length=80)] = "",
    limit: Annotated[int, Query(ge=1, le=8)] = 8,
) -> SuggestionList:
    """Suggest public titles, names, categories, and tags. At least two characters are required."""

    try:
        return search_service.suggestions(session, settings, request, query=q, limit=limit)
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/admin/stats",
    response_model=SearchStats,
    summary="Search statistics",
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
)
def stats(_admin: AdminUser, session: DatabaseSession) -> SearchStats:
    """Return search totals for the last 30 days. Individual searchers are not identified."""

    return search_service.search_stats(session)


@router.get("", response_model=SearchResponse, summary="Search public content", responses=_ERRORS)
def search(
    session: DatabaseSession,
    q: Annotated[str, Query(max_length=200)] = "",
    type: Annotated[SearchType, Query()] = "all",
    category: Annotated[str | None, Query(max_length=120)] = None,
    tag: Annotated[str | None, Query(max_length=120)] = None,
    author: Annotated[str | None, Query(max_length=30)] = None,
    publication: Annotated[str | None, Query(max_length=120)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: Annotated[ArticleSort, Query()] = "relevance",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchResponse:
    """Search public articles and directories.

    An empty query returns the latest public articles and leaves the other sections empty.
    A query without any word characters returns empty sections. Ranking scores are not included.
    """

    try:
        return search_service.search(
            session,
            query=q,
            search_type=type,
            category=category,
            tag=tag,
            author=author,
            publication=publication,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except ServiceError as exc:
        _raise(exc)


@discovery_router.get(
    "/articles",
    response_model=ArticleCardPage,
    summary="Discover articles",
)
def discover_articles(
    session: DatabaseSession,
    feed: Annotated[ArticleFeed, Query()] = "latest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ArticleCardPage:
    """Return latest, trending, popular, most discussed, or featured public articles."""

    return search_service.discover_articles(session, feed=feed, page=page, page_size=page_size)


@discovery_router.get(
    "/authors",
    response_model=AuthorCardPage,
    summary="Discover authors",
)
def discover_authors(
    session: DatabaseSession,
    q: Annotated[str, Query(max_length=80)] = "",
    category: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuthorCardPage:
    """Return public authors who have published at least one listed article."""

    return search_service.discover_authors(
        session, query=q, category=category, page=page, page_size=page_size
    )


@discovery_router.get(
    "/publications",
    response_model=PublicationCardPage,
    summary="Discover publications",
)
def discover_publications(
    session: DatabaseSession,
    q: Annotated[str, Query(max_length=80)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PublicationCardPage:
    """Return active public publications that have at least one listed article."""

    return search_service.discover_publications(
        session, query=q, page=page, page_size=page_size
    )
