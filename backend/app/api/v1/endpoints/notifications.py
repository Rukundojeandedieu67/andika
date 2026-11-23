"""Private notification routes. Clients cannot create notification events."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, CurrentUser, DatabaseSession, SettingsDep
from app.core.rate_limit import limit_notification_writes
from app.models.notification import NotificationType
from app.schemas.common import ErrorResponse
from app.schemas.notification import (
    DeliveryStats,
    NotificationPage,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
    ReadAllResult,
    UnreadCount,
)
from app.services import notification_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=NotificationPage, summary="List my notifications")
def list_notifications(
    actor: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    unread_only: bool = False,
    notification_type: Annotated[NotificationType | None, Query(alias="type")] = None,
) -> NotificationPage:
    """Return the caller's in-app notifications, newest first."""

    return notification_service.list_notifications(
        session,
        actor,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
        kind=notification_type,
    )


@router.get("/unread-count", response_model=UnreadCount, summary="Unread notification count")
def unread_count(actor: CurrentUser, session: DatabaseSession) -> UnreadCount:
    return UnreadCount(unread=notification_service.unread_count(session, actor))


@router.get(
    "/preferences",
    response_model=NotificationPreferenceRead,
    summary="Notification preferences",
)
def read_preferences(actor: CurrentUser, session: DatabaseSession) -> NotificationPreferenceRead:
    return notification_service.get_preferences(session, actor)


@router.patch(
    "/preferences",
    response_model=NotificationPreferenceRead,
    summary="Update notification preferences",
    responses=_ERRORS,
)
def update_preferences(
    payload: NotificationPreferenceUpdate,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> NotificationPreferenceRead:
    limit_notification_writes(settings, str(actor.id))
    return notification_service.update_preferences(session, actor, payload)


@router.post(
    "/read-all",
    response_model=ReadAllResult,
    summary="Mark all notifications read",
    responses=_ERRORS,
)
def read_all(
    actor: CurrentUser, session: DatabaseSession, settings: SettingsDep
) -> ReadAllResult:
    limit_notification_writes(settings, str(actor.id))
    return notification_service.mark_all_read(session, actor)


@router.get(
    "/admin/delivery",
    response_model=DeliveryStats,
    summary="Notification delivery statistics",
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
)
def delivery_stats(_admin: AdminUser, session: DatabaseSession) -> DeliveryStats:
    """Return outbox counts and failed jobs. Addresses and message bodies are omitted."""

    return notification_service.delivery_stats(session)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark a notification read",
    responses=_ERRORS,
)
def mark_read(
    notification_id: UUID,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> NotificationRead:
    limit_notification_writes(settings, str(actor.id))
    try:
        return notification_service.mark_read(session, actor, notification_id)
    except ServiceError as exc:
        _raise(exc)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification",
    responses=_ERRORS,
)
def delete_notification(
    notification_id: UUID,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> Response:
    limit_notification_writes(settings, str(actor.id))
    try:
        notification_service.delete_notification(session, actor, notification_id)
    except ServiceError as exc:
        _raise(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
