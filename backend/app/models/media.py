"""Uploaded images and their generated variants."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime
from app.models.user import User


class MediaStatus(str, enum.Enum):
    """Processing state. Public delivery requires READY."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class StorageProvider(str, enum.Enum):
    """Where the bytes are stored. The API never returns provider credentials."""

    LOCAL = "local"
    S3 = "s3"


class MediaVariantKind(str, enum.Enum):
    """Generated image sizes. Edges are maximums, not forced dimensions."""

    ORIGINAL = "original"
    LARGE = "large"
    MEDIUM = "medium"
    THUMBNAIL = "thumbnail"


class Media(Base):
    """An image owned by one user. Articles reference it and are not deleted with it."""

    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'ready', 'failed')",
            name="status",
        ),
        CheckConstraint(
            "storage_provider IN ('local', 's3')",
            name="provider",
        ),
        Index("ix_media_owner_id_created_at", "owner_id", "created_at"),
        Index(
            "uq_media_owner_checksum_active",
            "owner_id",
            "checksum",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    storage_provider: Mapped[StorageProvider] = mapped_column(
        Enum(
            StorageProvider,
            name="storage_provider",
            native_enum=False,
            length=16,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_extension: Mapped[str] = mapped_column(String(8), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    alt_text: Mapped[str | None] = mapped_column(String(300))
    caption: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(200))
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[MediaStatus] = mapped_column(
        Enum(
            MediaStatus,
            name="media_status",
            native_enum=False,
            length=16,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
        index=True,
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
    storage_deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    owner: Mapped[User] = relationship("User")
    variants: Mapped[list[MediaVariant]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
        order_by="MediaVariant.kind",
    )


class MediaVariant(Base):
    """One stored rendition of a media item."""

    __tablename__ = "media_variants"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('original', 'large', 'medium', 'thumbnail')",
            name="kind",
        ),
        UniqueConstraint("media_id", "kind", name="uq_media_variants_media_id_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[MediaVariantKind] = mapped_column(
        Enum(
            MediaVariantKind,
            name="media_variant_kind",
            native_enum=False,
            length=16,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    media: Mapped[Media] = relationship(back_populates="variants")

    @property
    def url(self) -> str:
        """Public or signed delivery URL. Filesystem paths are never returned."""

        from app.core.config import get_settings
        from app.core.storage_config import get_storage

        settings = get_settings()
        if settings.storage_provider == "s3":
            return get_storage().get_url(self.storage_key)
        return f"{settings.api_v1_prefix}/media/{self.media_id}/files/{self.kind.value}"
