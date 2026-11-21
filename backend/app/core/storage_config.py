"""Build the configured storage adapter without coupling services to a provider."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.infrastructure.storage.base import Storage
from app.infrastructure.storage.local import LocalStorage
from app.infrastructure.storage.s3 import S3Storage

_storage: Storage | None = None
_signature: tuple[str, ...] | None = None
_override: Storage | None = None


def build_storage(settings: Settings) -> Storage:
    """Return a local or S3 adapter for the current settings."""

    if settings.storage_provider == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            public_base_url=settings.s3_public_base_url,
            delivery=settings.media_delivery,
            signed_url_seconds=settings.media_signed_url_seconds,
        )
    return LocalStorage(settings.media_storage_dir)


def get_storage() -> Storage:
    """Return the process storage adapter, or the test override when one is set."""

    if _override is not None:
        return _override
    global _storage, _signature
    settings = get_settings()
    signature = (
        settings.storage_provider,
        str(settings.media_storage_dir),
        settings.s3_bucket,
        settings.s3_region,
        settings.s3_endpoint_url,
        settings.media_delivery,
    )
    if _storage is None or _signature != signature:
        _storage = build_storage(settings)
        _signature = signature
    return _storage


def set_storage_override(storage: Storage | None) -> None:
    """Replace storage for one test. Pass None to use the configured adapter again."""

    global _override
    _override = storage
