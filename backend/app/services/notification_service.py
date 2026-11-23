"""Create and read notifications inside the caller's database transaction."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.notification import (
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationType,
)
from app.models.user import User
from app.schemas.notification import (
    DeliveryFailure,
    DeliveryStats,
    NotificationPage,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
    ReadAllResult,
)
from app.schemas.post import AuthorPublic
from app.services.exceptions import NotFoundError

_PATH = re.compile(r"^/api/v1/[A-Za-z0-9_./-]{1,240}$")
_SECRET_KEYS = {"token", "email", "password", "token_hash", "secret"}
_CATEGORIES = {
    "comment_": "comments",
    "publication_": "publications",
    "article_": "editorial",
}


def emit(
    session: Session,
    *,
    recipient_id: uuid.UUID,
    actor: User | None,
    kind: NotificationType,
    title: str,
    message: str,
    resource_type: str | None,
    resource_id: uuid.UUID | None,
    action_url: str | None,
    details: dict | None,
    idempotency_key: str,
) -> None:
    """Record one notification. A duplicate key is ignored without undoing the caller's work."""

    if actor is not None and actor.id == recipient_id:
        return
    preference = _preference(session, recipient_id)
    category = _category(kind)
    in_app = bool(getattr(preference, f"in_app_{category}"))
    send_email = bool(getattr(preference, f"email_{category}"))
    if not in_app and not send_email:
        return
    path = action_url if action_url and _PATH.fullmatch(action_url) else None
    row = Notification(
        recipient_id=recipient_id,
        actor_id=None if actor is None else actor.id,
        type=kind,
        title=_clip(title, 160),
        message=_clip(message, 500),
        resource_type=resource_type,
        resource_id=resource_id,
        action_url=path,
        details=_safe_details(details),
        in_app=in_app,
        is_read=False,
        idempotency_key=idempotency_key[:160],
    )
    nested = session.begin_nested()
    try:
        session.add(row)
        session.flush()
    except IntegrityError:
        nested.rollback()
        return
    if not send_email:
        return
    recipient = session.get(User, recipient_id)
    if recipient is None or not recipient.email:
        return
    session.add(
        NotificationDelivery(
            notification_id=row.id,
            recipient_email=recipient.email,
            subject=_clip(title, 200),
            body=_email_body(message, path),
            status=DeliveryStatus.PENDING,
            attempts=0,
            next_attempt_at=datetime.now(UTC),
        )
    )
    session.flush()


def list_notifications(
    session: Session,
    recipient: User,
    *,
    page: int,
    page_size: int,
    unread_only: bool,
    kind: NotificationType | None,
) -> NotificationPage:
    clauses = [Notification.recipient_id == recipient.id, Notification.in_app.is_(True)]
    if unread_only:
        clauses.append(Notification.is_read.is_(False))
    if kind is not None:
        clauses.append(Notification.type == kind)
    total = session.scalar(select(func.count(Notification.id)).where(*clauses))
    rows = (
        session.scalars(
            select(Notification)
            .options(joinedload(Notification.actor))
            .where(*clauses)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )
    return NotificationPage(
        items=[_read(row) for row in rows],
        page=page,
        page_size=page_size,
        total=int(total or 0),
    )


def unread_count(session: Session, recipient: User) -> int:
    total = session.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == recipient.id,
            Notification.in_app.is_(True),
            Notification.is_read.is_(False),
        )
    )
    return int(total or 0)


def mark_read(session: Session, recipient: User, notification_id: uuid.UUID) -> NotificationRead:
    row = _owned(session, recipient, notification_id)
    if not row.is_read:
        now = datetime.now(UTC)
        row.is_read = True
        row.read_at = now
        row.updated_at = now
        session.flush()
    return _read(row)


def mark_all_read(session: Session, recipient: User) -> ReadAllResult:
    now = datetime.now(UTC)
    result = session.execute(
        update(Notification)
        .where(
            Notification.recipient_id == recipient.id,
            Notification.in_app.is_(True),
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now, updated_at=now)
    )
    session.flush()
    return ReadAllResult(updated=int(result.rowcount or 0))


def delete_notification(session: Session, recipient: User, notification_id: uuid.UUID) -> None:
    row = _owned(session, recipient, notification_id)
    session.delete(row)
    session.flush()


def get_preferences(session: Session, recipient: User) -> NotificationPreferenceRead:
    return _preference_read(_preference(session, recipient.id))


def update_preferences(
    session: Session, recipient: User, payload: NotificationPreferenceUpdate
) -> NotificationPreferenceRead:
    row = session.get(NotificationPreference, recipient.id)
    if row is None:
        row = NotificationPreference(
            user_id=recipient.id,
            in_app_comments=True,
            email_comments=True,
            in_app_publications=True,
            email_publications=True,
            in_app_editorial=True,
            email_editorial=True,
            in_app_account=True,
            email_account=True,
        )
        session.add(row)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(row, field, value)
    row.updated_at = datetime.now(UTC)
    session.flush()
    return _preference_read(row)


def delivery_stats(session: Session) -> DeliveryStats:
    """Aggregate outbox counts. Message bodies and addresses are not included."""

    counts = dict(
        session.execute(
            select(NotificationDelivery.status, func.count(NotificationDelivery.id)).group_by(
                NotificationDelivery.status
            )
        ).all()
    )
    failed = session.execute(
        select(
            NotificationDelivery.id,
            Notification.type,
            NotificationDelivery.attempts,
            NotificationDelivery.last_error,
            NotificationDelivery.updated_at,
        )
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .where(NotificationDelivery.status == DeliveryStatus.FAILED)
        .order_by(NotificationDelivery.updated_at.desc())
        .limit(20)
    ).all()
    return DeliveryStats(
        pending=_count(counts, DeliveryStatus.PENDING),
        sending=_count(counts, DeliveryStatus.SENDING),
        sent=_count(counts, DeliveryStatus.SENT),
        failed=_count(counts, DeliveryStatus.FAILED),
        not_configured=_count(counts, DeliveryStatus.NOT_CONFIGURED),
        failed_jobs=[
            DeliveryFailure(
                id=delivery_id,
                notification_type=kind,
                attempts=int(attempts),
                last_error=error,
                updated_at=updated_at,
            )
            for delivery_id, kind, attempts, error, updated_at in failed
        ],
    )


def _owned(session: Session, recipient: User, notification_id: uuid.UUID) -> Notification:
    row = session.scalar(
        select(Notification)
        .options(joinedload(Notification.actor))
        .where(
            Notification.id == notification_id,
            Notification.recipient_id == recipient.id,
            Notification.in_app.is_(True),
        )
    )
    if row is None:
        raise NotFoundError("Notification not found.")
    return row


def _preference(session: Session, user_id: uuid.UUID) -> NotificationPreference:
    row = session.get(NotificationPreference, user_id)
    if row is not None:
        return row
    return NotificationPreference(
        user_id=user_id,
        in_app_comments=True,
        email_comments=True,
        in_app_publications=True,
        email_publications=True,
        in_app_editorial=True,
        email_editorial=True,
        in_app_account=True,
        email_account=True,
    )


def _preference_read(row: NotificationPreference) -> NotificationPreferenceRead:
    return NotificationPreferenceRead(
        in_app_comments=row.in_app_comments,
        email_comments=row.email_comments,
        in_app_publications=row.in_app_publications,
        email_publications=row.email_publications,
        in_app_editorial=row.in_app_editorial,
        email_editorial=row.email_editorial,
        in_app_account=row.in_app_account,
        email_account=row.email_account,
    )


def _read(row: Notification) -> NotificationRead:
    return NotificationRead(
        id=row.id,
        type=row.type,
        title=row.title,
        message=row.message,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        action_url=row.action_url,
        metadata=row.details or {},
        is_read=row.is_read,
        read_at=row.read_at,
        created_at=row.created_at,
        actor=None if row.actor is None else AuthorPublic.model_validate(row.actor),
    )


def _category(kind: NotificationType) -> str:
    for prefix, name in _CATEGORIES.items():
        if kind.value.startswith(prefix):
            return name
    return "account"


def _safe_details(details: dict | None) -> dict | None:
    if not details:
        return None
    cleaned: dict[str, str | int | bool] = {}
    for key, value in list(details.items())[:8]:
        if not isinstance(key, str) or key.casefold() in _SECRET_KEYS:
            continue
        if isinstance(value, (str, int, bool)) and not isinstance(value, bool):
            cleaned[key[:40]] = value if not isinstance(value, str) else value[:120]
        elif isinstance(value, bool):
            cleaned[key[:40]] = value
    return cleaned or None


def _email_body(message: str, action_url: str | None) -> str:
    lines = [_clip(message, 500), "", "Sign in to ANDIKA to read this notification."]
    if action_url:
        lines.append(f"Reference: {action_url}")
    return "\n".join(lines)


def _clip(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    return cleaned[:limit]


def _count(counts: dict, status: DeliveryStatus) -> int:
    for key, value in counts.items():
        if key == status or getattr(key, "value", None) == status.value:
            return int(value)
    return 0
