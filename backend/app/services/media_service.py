"""Upload, ownership, and deletion rules for images."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.infrastructure.storage.base import Storage, StorageError
from app.models.media import (
    Media,
    MediaStatus,
    MediaVariant,
    MediaVariantKind,
    StorageProvider,
)
from app.models.post import Post
from app.models.user import User, UserRole
from app.repositories.media_repository import MediaRepository
from app.schemas.media import MediaUpdate
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.image_processing_service import EncodedImage, process_image

logger = logging.getLogger("andika.media")

_DANGEROUS_SUFFIXES = {
    ".svg",
    ".html",
    ".htm",
    ".js",
    ".mjs",
    ".exe",
    ".dll",
    ".php",
    ".bat",
    ".cmd",
    ".sh",
    ".ps1",
}
_VARIANT_KINDS = {
    "original": MediaVariantKind.ORIGINAL,
    "large": MediaVariantKind.LARGE,
    "medium": MediaVariantKind.MEDIUM,
    "thumbnail": MediaVariantKind.THUMBNAIL,
}


def store_upload(
    session: Session,
    owner: User,
    *,
    filename: str | None,
    declared_mime: str | None,
    data: bytes,
    title: str | None,
    caption: str | None,
    alt_text: str | None,
    storage: Storage,
    settings: Settings,
) -> tuple[Media, bool]:
    """Process an upload and store it. The second value is False when content is reused."""

    safe_name = _safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix in _DANGEROUS_SUFFIXES:
        raise ServiceError("That file type is not allowed.", 422)
    checksum = hashlib.sha256(data).hexdigest()
    existing = MediaRepository(session).get_active_by_checksum(owner.id, checksum)
    if existing is not None and existing.status is MediaStatus.READY:
        return existing, False

    processed = process_image(data, declared_mime=declared_mime, settings=settings)
    media_id = uuid.uuid4()
    provider = (
        StorageProvider.S3 if settings.storage_provider == "s3" else StorageProvider.LOCAL
    )
    original_key = _key(owner.id, media_id, f"original{processed.original.extension}")
    encoded = {
        MediaVariantKind.ORIGINAL: (original_key, processed.original),
        MediaVariantKind.LARGE: (
            _key(owner.id, media_id, "large.webp"),
            processed.large,
        ),
        MediaVariantKind.MEDIUM: (
            _key(owner.id, media_id, "medium.webp"),
            processed.medium,
        ),
        MediaVariantKind.THUMBNAIL: (
            _key(owner.id, media_id, "thumbnail.webp"),
            processed.thumbnail,
        ),
    }
    saved: list[str] = []
    try:
        for key, image in encoded.values():
            storage.save(key, image.data, image.mime_type)
            saved.append(key)
        media = Media(
            id=media_id,
            owner_id=owner.id,
            original_filename=safe_name,
            storage_key=original_key,
            storage_provider=provider,
            mime_type=processed.original.mime_type,
            file_extension=processed.original.extension,
            file_size=len(data),
            width=processed.original.width,
            height=processed.original.height,
            alt_text=alt_text,
            caption=caption,
            title=title,
            checksum=checksum,
            status=MediaStatus.READY,
            variants=[
                _variant(media_id, kind, key, image)
                for kind, (key, image) in encoded.items()
            ],
        )
        return MediaRepository(session).add(media), True
    except StorageError as exc:
        _remove_saved(storage, saved)
        logger.error("Media upload storage failed (%s)", type(exc).__name__)
        raise ServiceError("The file could not be stored.", 503) from exc
    except IntegrityError as exc:
        session.rollback()
        _remove_saved(storage, saved)
        existing = MediaRepository(session).get_active_by_checksum(owner.id, checksum)
        if existing is not None:
            return existing, False
        logger.error("Media upload conflict (%s)", type(exc).__name__)
        raise ConflictError("That image could not be saved.") from exc
    except Exception:
        _remove_saved(storage, saved)
        raise


def list_mine(
    session: Session,
    owner: User,
    *,
    page: int,
    page_size: int,
    search: str | None,
    mime_type: str | None,
) -> tuple[list[Media], int]:
    """Return the caller's media, excluding deleted records."""

    return MediaRepository(session).page_for_owner(
        owner.id,
        page=page,
        page_size=page_size,
        search=search,
        mime_type=mime_type,
    )


def list_all(
    session: Session,
    *,
    page: int,
    page_size: int,
    search: str | None,
    mime_type: str | None,
    owner_id: uuid.UUID | None,
    status: MediaStatus | None,
) -> tuple[list[Media], int]:
    """Return every media record that has not been deleted."""

    return MediaRepository(session).page_all(
        page=page,
        page_size=page_size,
        search=search,
        mime_type=mime_type,
        owner_id=owner_id,
        status=status,
    )


def get_visible(session: Session, media_id: uuid.UUID, actor: User) -> Media:
    """Return media the actor owns, or any media when the actor is an administrator."""

    media = MediaRepository(session).get(media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError("Media not found.")
    if actor.role is not UserRole.ADMIN and media.owner_id != actor.id:
        raise NotFoundError("Media not found.")
    return media


def update_metadata(
    session: Session, media_id: uuid.UUID, actor: User, payload: MediaUpdate
) -> Media:
    """Change title, caption, or alt text."""

    media = get_visible(session, media_id, actor)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(media, field, value)
    media.updated_at = datetime.now(UTC)
    session.flush()
    return media


def delete_media(
    session: Session, media_id: uuid.UUID, actor: User, storage: Storage
) -> None:
    """Remove stored files, then record the deletion. A storage failure leaves the record."""

    media = get_visible(session, media_id, actor)
    if _is_referenced(session, media.id):
        raise ConflictError("Detach this image from articles before deleting it.")
    keys = [variant.storage_key for variant in media.variants]
    if media.storage_key not in keys:
        keys.append(media.storage_key)
    try:
        for key in keys:
            storage.delete(key)
    except StorageError as exc:
        logger.error("Media file removal failed for %s (%s)", media.id, type(exc).__name__)
        raise ServiceError("The stored file could not be removed.", 503) from exc
    now = datetime.now(UTC)
    media.deleted_at = now
    media.storage_deleted_at = now
    media.updated_at = now
    session.flush()


def require_attachable(session: Session, media_id: uuid.UUID, actor: User) -> Media:
    """Return media that this actor may feature on an article."""

    media = MediaRepository(session).get(media_id)
    if media is None or media.deleted_at is not None:
        raise NotFoundError("Media not found.")
    if actor.role is not UserRole.ADMIN and media.owner_id != actor.id:
        raise NotFoundError("Media not found.")
    if media.status is not MediaStatus.READY or media.storage_deleted_at is not None:
        raise ServiceError("That image is not available.", 422)
    return media


def variant_url(media: Media, kind: str = "large") -> str:
    """Return the delivery URL for one rendition."""

    wanted = _VARIANT_KINDS.get(kind, MediaVariantKind.LARGE)
    for variant in media.variants:
        if variant.kind is wanted or variant.kind == wanted.value:
            return variant.url
    raise ServiceError("That image is not available.", 422)


def can_deliver(session: Session, media: Media, actor: User | None) -> bool:
    """Allow the owner, an administrator, or a published article to deliver the file."""

    if (
        media.deleted_at is not None
        or media.storage_deleted_at is not None
        or media.status is not MediaStatus.READY
    ):
        return False
    if actor is not None and (
        actor.role is UserRole.ADMIN or actor.id == media.owner_id
    ):
        return True
    return _is_published(session, media.id) or _is_public_branding(session, media.id)


def variant_for(media: Media, kind: str) -> MediaVariant | None:
    """Return one rendition by its public name."""

    wanted = _VARIANT_KINDS.get(kind)
    if wanted is None:
        return None
    for variant in media.variants:
        if variant.kind is wanted or variant.kind == wanted.value:
            return variant
    return None


def _is_referenced(session: Session, media_id: uuid.UUID) -> bool:
    found = session.scalar(
        select(Post.id)
        .where(Post.featured_image_id == media_id, Post.deleted_at.is_(None))
        .limit(1)
    )
    return found is not None


def _is_published(session: Session, media_id: uuid.UUID) -> bool:
    from app.services.visibility import is_publicly_listed

    posts = session.scalars(
        select(Post).where(
            Post.featured_image_id == media_id,
            Post.deleted_at.is_(None),
        )
    ).all()
    return any(is_publicly_listed(session, post) for post in posts)


def _is_public_branding(session: Session, media_id: uuid.UUID) -> bool:
    from app.models.publication import (
        Publication,
        PublicationStatus,
        PublicationVisibility,
    )

    found = session.scalar(
        select(Publication.id).where(
            Publication.deleted_at.is_(None),
            Publication.status == PublicationStatus.ACTIVE,
            Publication.visibility == PublicationVisibility.PUBLIC,
            or_(
                Publication.logo_media_id == media_id,
                Publication.cover_media_id == media_id,
            ),
        )
    )
    return found is not None


def _variant(
    media_id: uuid.UUID, kind: MediaVariantKind, key: str, image: EncodedImage
) -> MediaVariant:
    return MediaVariant(
        media_id=media_id,
        kind=kind,
        storage_key=key,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        file_size=len(image.data),
    )


def _key(owner_id: uuid.UUID, media_id: uuid.UUID, name: str) -> str:
    return f"media/{owner_id}/{media_id}/{name}"


def _safe_filename(filename: str | None) -> str:
    candidate = Path(filename or "image").name.replace("\x00", "").strip()
    if candidate in {"", ".", ".."}:
        return "image"
    return candidate[:255]


def _remove_saved(storage: Storage, keys: list[str]) -> None:
    for key in keys:
        try:
            storage.delete(key)
        except StorageError:
            logger.error("Uploaded file cleanup failed")
