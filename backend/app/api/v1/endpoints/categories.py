"""Public and administrative category routes.

Categories are global platform resources. Verified administrators create,
edit, activate, and delete them. Authors select an existing category when
editing an article and cannot change the catalog.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, DatabaseSession
from app.schemas.category import (
    CategoryAdmin,
    CategoryCreate,
    CategoryDetail,
    CategoryNode,
    CategoryPage,
    CategoryStatusUpdate,
    CategoryUpdate,
)
from app.schemas.common import ErrorResponse
from app.schemas.post import PostListParams, PostPage, PostRead
from app.services import category_service, post_service
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


@router.get("", response_model=list[CategoryNode], summary="List public categories")
def list_categories(session: DatabaseSession) -> list[CategoryNode]:
    """Return active categories whose parent categories are also active."""

    return category_service.public_tree(session)


@router.get(
    "/admin/all",
    response_model=CategoryPage,
    summary="List every category",
    responses=_ERRORS,
)
def list_all_categories(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CategoryPage:
    """Return active and inactive categories for an administrator."""

    items, total = category_service.list_admin(session, page=page, page_size=page_size)
    return CategoryPage(
        items=[CategoryAdmin.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=CategoryAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
    responses=_ERRORS,
)
def create_category(
    payload: CategoryCreate, _: AdminUser, session: DatabaseSession
) -> CategoryAdmin:
    """Create a global category. Authors and readers cannot call this route."""

    try:
        category = category_service.create_category(session, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return CategoryAdmin.model_validate(category)


@router.patch(
    "/admin/{category_id}/status",
    response_model=CategoryAdmin,
    summary="Activate or deactivate a category",
    responses=_ERRORS,
)
def set_category_status(
    category_id: UUID,
    payload: CategoryStatusUpdate,
    _: AdminUser,
    session: DatabaseSession,
) -> CategoryAdmin:
    """Hide or restore a category without deleting it or its articles."""

    try:
        category = category_service.set_status(
            session, category_id, is_active=payload.is_active
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return CategoryAdmin.model_validate(category)


@router.delete(
    "/admin/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
    responses=_ERRORS,
)
def delete_category(
    category_id: UUID, _: AdminUser, session: DatabaseSession
) -> Response:
    """Delete a category that has no children. Articles remain and lose this category."""

    try:
        category_service.delete_category(session, category_id)
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{category_id}",
    response_model=CategoryAdmin,
    summary="Update a category",
    responses=_ERRORS,
)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    _: AdminUser,
    session: DatabaseSession,
) -> CategoryAdmin:
    """Change a category name, description, or parent. Administrators only."""

    try:
        category = category_service.update_category(session, category_id, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return CategoryAdmin.model_validate(category)


@router.get(
    "/{slug}",
    response_model=CategoryDetail,
    summary="Get a public category",
    responses=_ERRORS,
)
def get_category(slug: str, session: DatabaseSession) -> CategoryDetail:
    """Return one visible category, its parent, and its visible children."""

    try:
        return category_service.get_public(session, slug)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.get(
    "/{slug}/posts",
    response_model=PostPage,
    summary="List published articles in a category",
    responses=_ERRORS,
)
def list_category_posts(
    slug: str,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PostPage:
    """Return published articles in this category and its visible child categories."""

    try:
        category_service.get_public(session, slug)
    except ServiceError as exc:
        _raise_service_error(exc)
    params = PostListParams(page=page, page_size=page_size, category=slug)
    items, total = post_service.list_published(session, params)
    return PostPage(
        items=[PostRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
