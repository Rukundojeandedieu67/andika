"""Administrator moderation routes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import AdminUser, DatabaseSession
from app.models.comment import CommentStatus
from app.models.comment_report import ReportStatus
from app.repositories.comment_report_repository import CommentReportRepository
from app.repositories.comment_repository import CommentRepository
from app.repositories.moderation_repository import ModerationRepository
from app.schemas.common import ErrorResponse
from app.schemas.moderation import (
    ModerationComment,
    ModerationCommentPage,
    ModerationLogPage,
    ModerationLogRead,
    ModerationStatusUpdate,
    ReportPage,
    ReportRead,
    ReportUpdate,
)
from app.services import moderation_service
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
    "/comments",
    response_model=ModerationCommentPage,
    summary="List comments for moderation",
    responses=_ERRORS,
)
def list_comments(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    comment_status: Annotated[CommentStatus | None, Query(alias="status")] = None,
    post_id: UUID | None = None,
    author_id: UUID | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> ModerationCommentPage:
    """Return comments across the platform, including ones that are not public."""

    items, total = CommentRepository(session).page_for_moderation(
        page=page,
        page_size=page_size,
        post_id=post_id,
        author_id=author_id,
        status=comment_status,
        search=search,
        created_from=created_from,
        created_to=created_to,
    )
    return ModerationCommentPage(
        items=[ModerationComment.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch(
    "/comments/{comment_id}/status",
    response_model=ModerationComment,
    summary="Change a comment's moderation status",
    responses=_ERRORS,
)
def set_comment_status(
    comment_id: UUID,
    payload: ModerationStatusUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> ModerationComment:
    """Approve, hide, reject, or restore a comment. The decision is written to the audit log."""

    try:
        comment = moderation_service.moderate_for_admin(
            session,
            comment_id=comment_id,
            actor=admin,
            status=payload.status,
            reason=payload.reason,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return ModerationComment.model_validate(comment)


@router.get(
    "/reports",
    response_model=ReportPage,
    summary="List comment reports",
    responses=_ERRORS,
)
def list_reports(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    report_status: Annotated[ReportStatus | None, Query(alias="status")] = None,
    post_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> ReportPage:
    """Return reports. Reporter email addresses are not included."""

    items, total = CommentReportRepository(session).page(
        page=page,
        page_size=page_size,
        status=report_status,
        post_id=post_id,
        created_from=created_from,
        created_to=created_to,
    )
    return ReportPage(
        items=[ReportRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch(
    "/reports/{report_id}",
    response_model=ReportRead,
    summary="Review a comment report",
    responses=_ERRORS,
)
def review_report(
    report_id: UUID,
    payload: ReportUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> ReportRead:
    """Resolve or dismiss a report. The comment is not deleted."""

    try:
        report = moderation_service.review_report(
            session,
            report_id=report_id,
            actor=admin,
            status=payload.status,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return ReportRead.model_validate(report)


@router.get(
    "/logs",
    response_model=ModerationLogPage,
    summary="List moderation history",
    responses=_ERRORS,
)
def list_logs(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    comment_id: UUID | None = None,
    moderator_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> ModerationLogPage:
    """Return moderation decisions. These records are not editable."""

    items, total = ModerationRepository(session).page(
        page=page,
        page_size=page_size,
        comment_id=comment_id,
        moderator_id=moderator_id,
        created_from=created_from,
        created_to=created_to,
    )
    return ModerationLogPage(
        items=[ModerationLogRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
