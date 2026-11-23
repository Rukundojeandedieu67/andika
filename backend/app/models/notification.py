"""In-app notifications, preferences, and the email outbox."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.user import User

_EVENT_VALUES = (
    "comment_received",
    "comment_reply_received",
    "comment_approved",
    "comment_hidden",
    "comment_rejected",
    "publication_invitation_received",
    "publication_invitation_accepted",
    "publication_member_role_changed",
    "publication_member_suspended",
    "publication_member_removed",
    "publication_ownership_transferred",
    "article_submitted_for_review",
    "article_review_started",
    "article_changes_requested",
    "article_approved",
    "article_published",
    "article_unpublished",
)
_DELIVERY_VALUES = ("pending", "sending", "sent", "failed", "not_configured")


class NotificationType(str, enum.Enum):
    """Events the application can record. Clients cannot invent new values."""

    COMMENT_RECEIVED = "comment_received"
    COMMENT_REPLY_RECEIVED = "comment_reply_received"
    COMMENT_APPROVED = "comment_approved"
    COMMENT_HIDDEN = "comment_hidden"
    COMMENT_REJECTED = "comment_rejected"
    PUBLICATION_INVITATION_RECEIVED = "publication_invitation_received"
    PUBLICATION_INVITATION_ACCEPTED = "publication_invitation_accepted"
    PUBLICATION_MEMBER_ROLE_CHANGED = "publication_member_role_changed"
    PUBLICATION_MEMBER_SUSPENDED = "publication_member_suspended"
    PUBLICATION_MEMBER_REMOVED = "publication_member_removed"
    PUBLICATION_OWNERSHIP_TRANSFERRED = "publication_ownership_transferred"
    ARTICLE_SUBMITTED_FOR_REVIEW = "article_submitted_for_review"
    ARTICLE_REVIEW_STARTED = "article_review_started"
    ARTICLE_CHANGES_REQUESTED = "article_changes_requested"
    ARTICLE_APPROVED = "article_approved"
    ARTICLE_PUBLISHED = "article_published"
    ARTICLE_UNPUBLISHED = "article_unpublished"


class DeliveryStatus(str, enum.Enum):
    """Email outbox state. Sent means the mail service confirmed delivery."""

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


def _enum(kind: type[enum.Enum], name: str, length: int) -> Enum:
    return Enum(
        kind,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda items: [item.value for item in items],
    )


class Notification(Base):
    """One recipient's private record of a platform event."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN (" + ", ".join(repr(value) for value in _EVENT_VALUES) + ")",
            name="type",
        ),
        Index("ix_notifications_recipient_id_created_at", "recipient_id", "created_at"),
        Index("ix_notifications_recipient_id_is_read", "recipient_id", "is_read"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        _enum(NotificationType, "notification_event_type", 48), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    action_url: Mapped[str | None] = mapped_column(String(300))
    details: Mapped[dict | None] = mapped_column("metadata", JSON)
    in_app: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])


class NotificationPreference(Base):
    """Per-account delivery choices. Missing rows use the default of enabled."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    in_app_comments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_comments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_publications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_publications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_editorial: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_editorial: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_account: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_account: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class NotificationDelivery(Base):
    """One email attempt for a notification. SMTP runs outside the business transaction."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(repr(value) for value in _DELIVERY_VALUES) + ")",
            name="status",
        ),
        Index(
            "ix_notification_deliveries_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum(DeliveryStatus, "notification_delivery_status", 24),
        default=DeliveryStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(80))
    next_attempt_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    notification: Mapped[Notification] = relationship()
