"""ORM models.

Import each model module here so Alembic autogenerate can discover its tables.
"""

from app.database.base import Base
from app.models.auth_session import AuthSession
from app.models.auth_token import EmailVerificationToken, PasswordResetToken
from app.models.category import Category
from app.models.media import Media, MediaStatus, MediaVariant, StorageProvider
from app.models.post import Post, PostRedirect, PostStatus
from app.models.post_revision import PostRevision
from app.models.tag import Tag
from app.models.user import User, UserRole

__all__ = [
    "AuthSession",
    "Base",
    "Category",
    "EmailVerificationToken",
    "Media",
    "MediaStatus",
    "MediaVariant",
    "PasswordResetToken",
    "Post",
    "PostRedirect",
    "PostRevision",
    "PostStatus",
    "StorageProvider",
    "Tag",
    "User",
    "UserRole",
]
