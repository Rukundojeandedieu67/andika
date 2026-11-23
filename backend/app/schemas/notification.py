"""Public notification responses. Delivery addresses are not included."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationType
from app.schemas.post import AuthorPublic


class NotificationRead(BaseModel):
    """A notification the caller is allowed to see."""

    id: UUID
    type: NotificationType
    title: str
    message: str
    resource_type: str | None
    resource_id: UUID | None
    action_url: str | None
    metadata: dict = Field(default_factory=dict)
    is_read: bool
    read_at: datetime | None
    created_at: datetime
    actor: AuthorPublic | None = None


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    page: int
    page_size: int
    total: int


class UnreadCount(BaseModel):
    unread: int


class ReadAllResult(BaseModel):
    updated: int


class NotificationPreferenceRead(BaseModel):
    in_app_comments: bool
    email_comments: bool
    in_app_publications: bool
    email_publications: bool
    in_app_editorial: bool
    email_editorial: bool
    in_app_account: bool
    email_account: bool


class NotificationPreferenceUpdate(BaseModel):
    """Partial preference update. Omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")

    in_app_comments: bool | None = None
    email_comments: bool | None = None
    in_app_publications: bool | None = None
    email_publications: bool | None = None
    in_app_editorial: bool | None = None
    email_editorial: bool | None = None
    in_app_account: bool | None = None
    email_account: bool | None = None


class DeliveryFailure(BaseModel):
    """A failed email job without the address or message body."""

    id: UUID
    notification_type: NotificationType
    attempts: int
    last_error: str | None
    updated_at: datetime


class DeliveryStats(BaseModel):
    pending: int
    sending: int
    sent: int
    failed: int
    not_configured: int
    failed_jobs: list[DeliveryFailure]
