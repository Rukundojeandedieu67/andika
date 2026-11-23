"""Public discussions and comment ownership routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import CurrentUser, DatabaseSession, SettingsDep
from app.core.rate_limit import limit_comments, limit_reports
from app.repositories.comment_report_repository import CommentReportRepository
from app.repositories.comment_repository import CommentRepository
from app.schemas.comment import (
    CommentCreate,
    CommentOwned,
    CommentOwnedPage,
    CommentPage,
    CommentUpdate,
)
from app.schemas.common import ErrorResponse
from app.schemas.moderation import (
    ModerationComment,
    ModerationCommentPage,
    ModerationStatusUpdate,
    ReportCreate,
    ReportPage,
    ReportRead,
    ReportUpdate,
)
from app.services import comment_service, moderation_service
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


@router.get(
    "/posts/{post_id}/comments",
    response_model=CommentPage,
    summary="List approved comments",
    responses=_ERRORS,
)
def list_comments(
    post_id: UUID,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CommentPage:
    """Return approved threads for a published article. Replies are nested one level."""

    try:
        items, total = comment_service.list_public(
            session, post_id, page=page, page_size=page_size
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return CommentPage(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentOwned,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment",
    responses=_ERRORS,
)
def create_comment(
    post_id: UUID,
    payload: CommentCreate,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> CommentOwned:
    """Add a root comment. Verified accounts are approved. Others stay pending."""

    limit_comments(settings, str(actor.id))
    try:
        comment = comment_service.create_comment(
            session, post_id=post_id, author=actor, body=payload.body
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return CommentOwned.model_validate(comment)


@router.post(
    "/posts/{post_id}/comments/{comment_id}/replies",
    response_model=CommentOwned,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to a comment",
    responses=_ERRORS,
)
def create_reply(
    post_id: UUID,
    comment_id: UUID,
    payload: CommentCreate,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> CommentOwned:
    """Reply to an approved root comment. A reply cannot contain another reply."""

    limit_comments(settings, str(actor.id))
    try:
        comment = comment_service.create_comment(
            session,
            post_id=post_id,
            author=actor,
            body=payload.body,
            parent_id=comment_id,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return CommentOwned.model_validate(comment)


@router.get(
    "/comments/mine",
    response_model=CommentOwnedPage,
    summary="List my comments",
    responses=_ERRORS,
)
def list_my_comments(
    actor: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CommentOwnedPage:
    """Return the caller's comments, including ones that are not public yet."""

    items, total = comment_service.list_mine(
        session, actor, page=page, page_size=page_size
    )
    return CommentOwnedPage(
        items=[CommentOwned.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentOwned,
    summary="Edit a comment",
    responses=_ERRORS,
)
def update_comment(
    comment_id: UUID,
    payload: CommentUpdate,
    actor: CurrentUser,
    session: DatabaseSession,
) -> CommentOwned:
    """Change the body of a comment the caller wrote."""

    try:
        comment = comment_service.update_comment(session, comment_id, actor, payload.body)
    except ServiceError as exc:
        _raise_service_error(exc)
    return CommentOwned.model_validate(comment)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
    responses=_ERRORS,
)
def delete_comment(
    comment_id: UUID, actor: CurrentUser, session: DatabaseSession
) -> Response:
    """Soft-delete a comment the caller wrote. Replies and attribution stay."""

    try:
        comment_service.delete_comment(session, comment_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/comments/{comment_id}/report",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Report a comment",
    responses=_ERRORS,
)
def report_comment(
    comment_id: UUID,
    payload: ReportCreate,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> ReportRead:
    """Ask for a review. The comment is not deleted by the report."""

    limit_reports(settings, str(actor.id))
    try:
        report = moderation_service.create_report(
            session,
            comment_id=comment_id,
            reporter=actor,
            reason=payload.reason,
            description=payload.description,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return ReportRead.model_validate(report)


@router.get(
    "/posts/{post_id}/moderation/comments",
    response_model=ModerationCommentPage,
    summary="Review comments on my article",
    responses=_ERRORS,
)
def list_article_comments(
    post_id: UUID,
    actor: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    comment_status: Annotated[str | None, Query(alias="status")] = None,
) -> ModerationCommentPage:
    """Return every comment on an article the caller wrote."""

    try:
        moderation_service.require_article_author(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    status_filter = _status_filter(comment_status)
    items, total = CommentRepository(session).page_for_moderation(
        page=page,
        page_size=page_size,
        post_id=post_id,
        author_id=None,
        status=status_filter,
        search=None,
        created_from=None,
        created_to=None,
    )
    return _comment_page(items, page, page_size, total)


@router.patch(
    "/posts/{post_id}/moderation/comments/{comment_id}/status",
    response_model=ModerationComment,
    summary="Moderate a comment on my article",
    responses=_ERRORS,
)
def moderate_article_comment(
    post_id: UUID,
    comment_id: UUID,
    payload: ModerationStatusUpdate,
    actor: CurrentUser,
    session: DatabaseSession,
) -> ModerationComment:
    """Approve or hide a comment, or restore a hidden one. Authors cannot reject."""

    try:
        comment = moderation_service.moderate_for_author(
            session,
            post_id=post_id,
            comment_id=comment_id,
            actor=actor,
            status=payload.status,
            reason=payload.reason,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return ModerationComment.model_validate(comment)


@router.get(
    "/posts/{post_id}/moderation/reports",
    response_model=ReportPage,
    summary="Review reports on my article",
    responses=_ERRORS,
)
def list_article_reports(
    post_id: UUID,
    actor: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReportPage:
    """Return reports for comments on an article the caller wrote."""

    try:
        moderation_service.require_article_author(session, post_id, actor)
    except ServiceError as exc:
        _raise_service_error(exc)
    items, total = CommentReportRepository(session).page(
        page=page,
        page_size=page_size,
        status=None,
        post_id=post_id,
        created_from=None,
        created_to=None,
    )
    return ReportPage(
        items=[ReportRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch(
    "/posts/{post_id}/moderation/reports/{report_id}",
    response_model=ReportRead,
    summary="Resolve a report on my article",
    responses=_ERRORS,
)
def review_article_report(
    post_id: UUID,
    report_id: UUID,
    payload: ReportUpdate,
    actor: CurrentUser,
    session: DatabaseSession,
) -> ReportRead:
    """Resolve or dismiss a report. The comment itself is unchanged."""

    try:
        report = moderation_service.review_report(
            session,
            report_id=report_id,
            actor=actor,
            status=payload.status,
            post_id=post_id,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return ReportRead.model_validate(report)


def _status_filter(value: str | None):
    if value is None:
        return None
    from app.models.comment import CommentStatus

    try:
        return CommentStatus(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Status must be pending, approved, hidden, or rejected.",
        ) from exc


def _comment_page(items, page: int, page_size: int, total: int) -> ModerationCommentPage:
    return ModerationCommentPage(
        items=[ModerationComment.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
