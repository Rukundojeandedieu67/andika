"""Public and editorial article routes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.dependencies import (
    AdminUser,
    AuthorUser,
    DatabaseSession,
    OptionalUser,
    SettingsDep,
    VerifiedUser,
)
from app.models.post import Post, PostStatus
from app.schemas.common import ErrorResponse
from app.schemas.editorial import ChangeRequest
from app.schemas.post import PostCreate, PostListParams, PostPage, PostRead, PostUpdate
from app.schemas.post_revision import PostRevisionRead
from app.schemas.search import ArticleCardPage
from app.services import editorial_service, post_service, search_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
}


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _page(items: list[Post], params: PostListParams, total: int) -> PostPage:
    return PostPage(
        items=[PostRead.model_validate(item) for item in items],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get("", response_model=PostPage, summary="List published articles")
def list_posts(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
    author_id: UUID | None = None,
    featured: bool | None = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    tag: Annotated[str | None, Query(max_length=120)] = None,
) -> PostPage:
    """Return published articles. Drafts, archived articles, and deletions are excluded."""

    params = PostListParams(
        page=page,
        page_size=page_size,
        search=search,
        author_id=author_id,
        featured=featured,
        category=category,
        tag=tag,
    )
    items, total = post_service.list_published(session, params)
    return _page(items, params, total)


@router.post(
    "",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft",
    responses=_ERRORS,
)
def create_post(
    payload: PostCreate, author: VerifiedUser, session: DatabaseSession
) -> PostRead:
    """Create a draft for the authenticated author. The client cannot choose the author."""

    try:
        post = post_service.create_draft(session, author, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.get(
    "/mine", response_model=PostPage, summary="List my articles", responses=_ERRORS
)
def list_my_posts(
    author: AuthorUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> PostPage:
    """Return the caller's drafts, published articles, and archived articles."""

    params = PostListParams(page=page, page_size=page_size, search=search)
    items, total = post_service.list_mine(session, author, params)
    return _page(items, params, total)


@router.get(
    "/mine/{post_id}",
    response_model=PostRead,
    summary="Get my article",
    responses=_ERRORS,
)
def read_my_post(
    post_id: UUID, author: AuthorUser, session: DatabaseSession
) -> PostRead:
    """Return one article owned by the caller, including drafts and archived articles."""

    try:
        post = post_service.get_owned(session, post_id, author)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.get(
    "/admin/all",
    response_model=PostPage,
    summary="List every article",
    responses=_ERRORS,
)
def list_all_posts(
    _admin: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
    author_id: UUID | None = None,
    status_filter: Annotated[PostStatus | None, Query(alias="status")] = None,
    published_from: datetime | None = None,
    published_to: datetime | None = None,
) -> PostPage:
    """Return drafts, published articles, and archived articles for an administrator."""

    params = PostListParams(
        page=page,
        page_size=page_size,
        search=search,
        author_id=author_id,
        status=status_filter,
        published_from=published_from,
        published_to=published_to,
    )
    items, total = post_service.list_all(session, params)
    return _page(items, params, total)


@router.get(
    "/{slug}",
    response_model=PostRead,
    summary="Read a published article",
    responses={
        status.HTTP_301_MOVED_PERMANENTLY: {
            "description": "The article has a newer slug."
        },
        **_ERRORS,
    },
)
def read_post(slug: str, session: DatabaseSession) -> PostRead | RedirectResponse:
    """Return one published article. An old slug redirects to the current one."""

    try:
        found = post_service.get_published_by_slug(session, slug)
    except ServiceError as exc:
        _raise_service_error(exc)
    if isinstance(found, str):
        settings = get_settings()
        return RedirectResponse(
            url=f"{settings.api_v1_prefix}/posts/{found}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )
    return PostRead.model_validate(found)


@router.patch(
    "/{post_id}",
    response_model=PostRead,
    summary="Update an article",
    responses=_ERRORS,
)
def update_post(
    post_id: UUID,
    payload: PostUpdate,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> PostRead:
    """Update an article the caller is allowed to edit."""

    try:
        post = post_service.update_post(session, post_id, actor, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{post_id}/publish",
    response_model=PostRead,
    summary="Publish a draft",
    responses=_ERRORS,
)
def publish_post(
    post_id: UUID, actor: VerifiedUser, session: DatabaseSession
) -> PostRead:
    """Publish a draft owned by the caller. Administrators can publish any draft."""

    try:
        post = post_service.publish_post(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{post_id}/unpublish",
    response_model=PostRead,
    summary="Unpublish an article",
    responses=_ERRORS,
)
def unpublish_post(
    post_id: UUID, actor: VerifiedUser, session: DatabaseSession
) -> PostRead:
    """Return a published article to draft."""

    try:
        post = post_service.unpublish_post(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{post_id}/archive",
    response_model=PostRead,
    summary="Archive an article",
    responses=_ERRORS,
)
def archive_post(
    post_id: UUID, actor: VerifiedUser, session: DatabaseSession
) -> PostRead:
    """Archive an article so it is no longer public."""

    try:
        post = post_service.archive_post(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an article",
    responses=_ERRORS,
)
def delete_post(post_id: UUID, actor: VerifiedUser, session: DatabaseSession) -> Response:
    """Soft-delete an article. It disappears from public and editorial listings."""

    try:
        post_service.delete_post(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{post_id}/revisions",
    response_model=list[PostRevisionRead],
    summary="List article revisions",
    responses=_ERRORS,
)
def read_revisions(
    post_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> list[PostRevisionRead]:
    """Return previous content for an article the caller can edit."""

    try:
        revisions = post_service.list_post_revisions(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return [PostRevisionRead.model_validate(item) for item in revisions]


@router.get(
    "/{post_id}/revisions/{revision_id}",
    response_model=PostRevisionRead,
    summary="Read one article revision",
    responses=_ERRORS,
)
def read_revision(
    post_id: UUID,
    revision_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> PostRevisionRead:
    """Return one previous version of an article the caller can edit."""

    try:
        revision = post_service.get_post_revision(session, post_id, revision_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRevisionRead.model_validate(revision)


@router.post(
    "/{post_id}/submit",
    response_model=PostRead,
    summary="Submit a publication article",
    responses=_ERRORS,
)
def submit_post(post_id: UUID, actor: VerifiedUser, session: DatabaseSession) -> PostRead:
    """Send the caller's publication draft to the editors."""

    try:
        post = editorial_service.submit_post(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{post_id}/start-review",
    response_model=PostRead,
    summary="Start editorial review",
    responses=_ERRORS,
)
def start_review(post_id: UUID, actor: VerifiedUser, session: DatabaseSession) -> PostRead:
    """Move a submitted publication article into review."""

    try:
        post = editorial_service.start_review(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{post_id}/request-changes",
    response_model=PostRead,
    summary="Request article changes",
    responses=_ERRORS,
)
def request_changes(
    post_id: UUID,
    payload: ChangeRequest,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> PostRead:
    """Ask the author to revise a submitted or in-review article."""

    try:
        post = editorial_service.request_changes(session, post_id, actor, payload.reason)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{post_id}/approve",
    response_model=PostRead,
    summary="Approve a publication article",
    responses=_ERRORS,
)
def approve_post(post_id: UUID, actor: VerifiedUser, session: DatabaseSession) -> PostRead:
    """Approve an article so an editor can publish it."""

    try:
        post = editorial_service.approve_post(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return PostRead.model_validate(post)


@router.post(
    "/{slug}/view",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record an article view",
    responses=_ERRORS,
)
def record_post_view(
    slug: str,
    session: DatabaseSession,
    settings: SettingsDep,
    viewer: OptionalUser,
    visitor_id: Annotated[str | None, Header(alias="X-Visitor-Id")] = None,
    source: Annotated[str | None, Query(max_length=40)] = None,
    user_agent: Annotated[str | None, Header()] = None,
) -> Response:
    """Count a public read. The response never includes the visitor."""

    try:
        search_service.record_view(
            session,
            settings,
            slug=slug,
            viewer=viewer,
            visitor_id=visitor_id,
            source=source,
            user_agent=user_agent,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{post_id}/related",
    response_model=ArticleCardPage,
    summary="Related articles",
    responses=_ERRORS,
)
def related_posts(
    post_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> ArticleCardPage:
    """Return public articles that share a category, tag, publication, or author."""

    try:
        return search_service.related_articles(session, post_id, limit=limit)
    except ServiceError as exc:
        _raise_service_error(exc)
