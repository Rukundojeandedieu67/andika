"""Publications, memberships, invitations, and publication audit history."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.media import Media
    from app.models.user import User


class PublicationVisibility(str, enum.Enum):
    """Who can see the publication profile and its published articles."""

    PUBLIC = "public"
    PRIVATE = "private"


class PublicationStatus(str, enum.Enum):
    """Operational state. Only active publications accept new editorial work."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class MembershipRole(str, enum.Enum):
    """Authority inside one publication. This is not a platform role."""

    OWNER = "owner"
    EDITOR = "editor"
    AUTHOR = "author"
    CONTRIBUTOR = "contributor"


class MembershipStatus(str, enum.Enum):
    """Whether a membership currently grants access."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class InvitationStatus(str, enum.Enum):
    """Lifecycle of a single-use invitation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


def _enum(enum_type: type[enum.Enum], name: str, length: int = 32) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda items: [item.value for item in items],
    )


class Publication(Base):
    """An editorial space. Independent articles do not need one."""

    __tablename__ = "publications"
    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'private')", name="visibility"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'archived')",
            name="status",
        ),
        Index("ix_publications_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media.id", ondelete="SET NULL"),
        index=True,
    )
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media.id", ondelete="SET NULL"),
        index=True,
    )
    website_url: Mapped[str | None] = mapped_column(String(500))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    visibility: Mapped[PublicationVisibility] = mapped_column(
        _enum(PublicationVisibility, "publication_visibility", 16),
        default=PublicationVisibility.PUBLIC,
        nullable=False,
        index=True,
    )
    status: Mapped[PublicationStatus] = mapped_column(
        _enum(PublicationStatus, "publication_status", 16),
        default=PublicationStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    editors_can_invite: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    logo_media: Mapped[Media | None] = relationship(foreign_keys=[logo_media_id])
    cover_media: Mapped[Media | None] = relationship(foreign_keys=[cover_media_id])
    memberships: Mapped[list[PublicationMembership]] = relationship(
        back_populates="publication"
    )


class PublicationMembership(Base):
    """One user's role in one publication."""

    __tablename__ = "publication_memberships"
    __table_args__ = (
        UniqueConstraint(
            "publication_id",
            "user_id",
            name="uq_publication_memberships_publication_id_user_id",
        ),
        CheckConstraint(
            "role IN ('owner', 'editor', 'author', 'contributor')",
            name="role",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended', 'removed')",
            name="status",
        ),
        Index(
            "uq_publication_memberships_one_owner",
            "publication_id",
            unique=True,
            sqlite_where=text("role = 'owner' AND status = 'active'"),
            postgresql_where=text("role = 'owner' AND status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[MembershipRole] = mapped_column(
        _enum(MembershipRole, "membership_role", 16),
        nullable=False,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        _enum(MembershipStatus, "membership_status", 16),
        default=MembershipStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    joined_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    publication: Mapped[Publication] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class PublicationInvitation(Base):
    """A hashed, expiring invitation. The raw token is never stored."""

    __tablename__ = "publication_invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('editor', 'author', 'contributor')",
            name="role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="status",
        ),
        Index(
            "uq_publication_invitations_pending_email",
            "publication_id",
            "email_key",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_key: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[MembershipRole] = mapped_column(
        _enum(MembershipRole, "invitation_role", 16),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        _enum(InvitationStatus, "invitation_status", 16),
        default=InvitationStatus.PENDING,
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    publication: Mapped[Publication] = relationship()
    invited_by: Mapped[User] = relationship(foreign_keys=[invited_by_id])


class PublicationAuditLog(Base):
    """Append-only record of publication management. APIs cannot edit or delete it."""

    __tablename__ = "publication_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(String(500))
    new_value: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    actor: Mapped[User] = relationship(foreign_keys=[actor_id])
    target: Mapped[User | None] = relationship(foreign_keys=[target_user_id])
