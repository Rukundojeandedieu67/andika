"""ORM models.

Import each model module here so Alembic autogenerate can discover its tables.
"""

from app.database.base import Base
from app.models.article_view import ArticleView
from app.models.auth_session import AuthSession
from app.models.auth_token import EmailVerificationToken, PasswordResetToken
from app.models.category import Category
from app.models.comment import Comment, CommentStatus
from app.models.comment_report import CommentReport, ReportReason, ReportStatus
from app.models.editorial import EditorialEvent, EditorialStatus
from app.models.media import Media, MediaStatus, MediaVariant, StorageProvider
from app.models.moderation_log import ModerationLog
from app.models.notification import (
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationType,
)
from app.models.post import Post, PostRedirect, PostStatus
from app.models.post_revision import PostRevision
from app.models.publication import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    Publication,
    PublicationAuditLog,
    PublicationInvitation,
    PublicationMembership,
    PublicationStatus,
    PublicationVisibility,
)
from app.models.search_event import SearchEvent
from app.models.tag import Tag
from app.models.user import User, UserRole

__all__ = [
    "ArticleView",
    "AuthSession",
    "Base",
    "Category",
    "Comment",
    "CommentReport",
    "CommentStatus",
    "DeliveryStatus",
    "EditorialEvent",
    "EditorialStatus",
    "EmailVerificationToken",
    "InvitationStatus",
    "Media",
    "MediaStatus",
    "MediaVariant",
    "MembershipRole",
    "MembershipStatus",
    "ModerationLog",
    "Notification",
    "NotificationDelivery",
    "NotificationPreference",
    "NotificationType",
    "PasswordResetToken",
    "Post",
    "PostRedirect",
    "PostRevision",
    "PostStatus",
    "Publication",
    "PublicationAuditLog",
    "PublicationInvitation",
    "PublicationMembership",
    "PublicationStatus",
    "PublicationVisibility",
    "ReportReason",
    "ReportStatus",
    "SearchEvent",
    "StorageProvider",
    "Tag",
    "User",
    "UserRole",
]
