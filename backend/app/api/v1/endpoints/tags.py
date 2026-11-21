"""Public, author, and administrative tag routes.

Authors may create reusable tags. Public lists include only tags used by a
published article. Administrators can see, rename, and delete every tag.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, AuthorUser, DatabaseSession
from app.schemas.common import ErrorResponse
from app.schemas.post import PostListParams, PostPage, PostRead
from app.schemas.tag import (
    TagAdmin,
    TagAdminPage,
    TagBrief,
    TagCreate,
    TagPage,
    TagUpdate,
)
from app.services import post_service, tag_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=TagPage, summary="List public tags")
def list_tags(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TagPage:
    """Return tags that appear on at least one published article."""

    items, total = tag_service.list_public(session, page=page, page_size=page_size)
    return TagPage(
        items=[TagBrief.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/admin/all",
    response_model=TagAdminPage,
    summary="List every tag",
    responses=_ERRORS,
)
def list_all_tags(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TagAdminPage:
    """Return every tag, including tags that are not used publicly yet."""

    items, total = tag_service.list_all(session, page=page, page_size=page_size)
    return TagAdminPage(
        items=[TagAdmin.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=TagAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    responses=_ERRORS,
)
def create_tag(
    payload: TagCreate, _: AuthorUser, session: DatabaseSession
) -> TagAdmin:
    """Create a reusable tag. Readers cannot call this route."""

    try:
        tag = tag_service.create_tag(session, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return TagAdmin.model_validate(tag)


@router.patch(
    "/admin/{tag_id}",
    response_model=TagAdmin,
    summary="Update a tag",
    responses=_ERRORS,
)
def update_tag(
    tag_id: UUID, payload: TagUpdate, _: AdminUser, session: DatabaseSession
) -> TagAdmin:
    """Rename a tag or change its description. Administrators only."""

    try:
        tag = tag_service.update_tag(session, tag_id, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return TagAdmin.model_validate(tag)


@router.delete(
    "/admin/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
    responses=_ERRORS,
)
def delete_tag(tag_id: UUID, _: AdminUser, session: DatabaseSession) -> Response:
    """Remove a tag and its article associations. Articles remain."""

    try:
        tag_service.delete_tag(session, tag_id)
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{slug}",
    response_model=TagBrief,
    summary="Get a public tag",
    responses=_ERRORS,
)
def get_tag(slug: str, session: DatabaseSession) -> TagBrief:
    """Return a tag that is used by a published article."""

    try:
        tag = tag_service.get_public(session, slug)
    except ServiceError as exc:
        _raise_service_error(exc)
    return TagBrief.model_validate(tag)


@router.get(
    "/{slug}/posts",
    response_model=PostPage,
    summary="List published articles with a tag",
    responses=_ERRORS,
)
def list_tag_posts(
    slug: str,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PostPage:
    """Return published articles that use this tag."""

    try:
        tag_service.get_public(session, slug)
    except ServiceError as exc:
        _raise_service_error(exc)
    params = PostListParams(page=page, page_size=page_size, tag=slug)
    items, total = post_service.list_published(session, params)
    return PostPage(
        items=[PostRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
