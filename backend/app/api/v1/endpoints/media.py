"""Image upload, library, and controlled file delivery."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse

from app.core.dependencies import (
    AdminUser,
    AuthorUser,
    DatabaseSession,
    OptionalUser,
    SettingsDep,
)
from app.core.rate_limit import limit_media_upload
from app.core.storage_config import get_storage
from app.infrastructure.storage.base import Storage, StorageError
from app.models.media import MediaStatus
from app.repositories.media_repository import MediaRepository
from app.schemas.common import ErrorResponse
from app.schemas.media import (
    MediaAdminPage,
    MediaAdminRead,
    MediaPage,
    MediaRead,
    MediaUpdate,
)
from app.services import media_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _storage() -> Storage:
    return get_storage()


@router.post(
    "/upload",
    response_model=MediaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image",
    responses=_ERRORS,
)
async def upload_media(
    author: AuthorUser,
    session: DatabaseSession,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    caption: Annotated[str | None, Form()] = None,
    alt_text: Annotated[str | None, Form()] = None,
) -> MediaRead | Response:
    """Upload a JPEG, PNG, or WebP image. Readers cannot call this route."""

    limit_media_upload(settings, str(author.id))
    metadata = MediaUpdate(title=title, caption=caption, alt_text=alt_text)
    try:
        data = await _read_limited(file, settings.media_max_upload_bytes)
        media, created = media_service.store_upload(
            session,
            author,
            filename=file.filename,
            declared_mime=file.content_type,
            data=data,
            title=metadata.title,
            caption=metadata.caption,
            alt_text=metadata.alt_text,
            storage=_storage(),
            settings=settings,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    body = MediaRead.model_validate(media)
    if created:
        return body
    return Response(
        status_code=status.HTTP_200_OK,
        content=body.model_dump_json(),
        media_type="application/json",
    )


@router.get(
    "/mine",
    response_model=MediaPage,
    summary="List my media",
    responses=_ERRORS,
)
def list_my_media(
    author: AuthorUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
    mime_type: Annotated[str | None, Query(max_length=64)] = None,
) -> MediaPage:
    """Return the caller's images, newest first. Deleted images are excluded."""

    items, total = media_service.list_mine(
        session,
        author,
        page=page,
        page_size=page_size,
        search=search,
        mime_type=mime_type,
    )
    return MediaPage(
        items=[MediaRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/admin/all",
    response_model=MediaAdminPage,
    summary="List every media record",
    responses=_ERRORS,
)
def list_all_media(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
    mime_type: Annotated[str | None, Query(max_length=64)] = None,
    owner_id: UUID | None = None,
    media_status: Annotated[MediaStatus | None, Query(alias="status")] = None,
) -> MediaAdminPage:
    """Return media across authors. Deleted records are excluded."""

    items, total = media_service.list_all(
        session,
        page=page,
        page_size=page_size,
        search=search,
        mime_type=mime_type,
        owner_id=owner_id,
        status=media_status,
    )
    return MediaAdminPage(
        items=[MediaAdminRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.delete(
    "/admin/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete any media record",
    responses=_ERRORS,
)
def admin_delete_media(
    media_id: UUID, admin: AdminUser, session: DatabaseSession
) -> Response:
    """Remove an image that is not attached to an article."""

    try:
        media_service.delete_media(session, media_id, admin, _storage())
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{media_id}",
    response_model=MediaRead,
    summary="Get media metadata",
    responses=_ERRORS,
)
def get_media(media_id: UUID, author: AuthorUser, session: DatabaseSession) -> MediaRead:
    """Return one image belonging to the caller, or any image for an administrator."""

    try:
        media = media_service.get_visible(session, media_id, author)
    except ServiceError as exc:
        _raise_service_error(exc)
    return MediaRead.model_validate(media)


@router.patch(
    "/{media_id}",
    response_model=MediaRead,
    summary="Update media metadata",
    responses=_ERRORS,
)
def update_media(
    media_id: UUID,
    payload: MediaUpdate,
    author: AuthorUser,
    session: DatabaseSession,
) -> MediaRead:
    """Change the title, caption, or alt text of an owned image."""

    try:
        media = media_service.update_metadata(session, media_id, author, payload)
    except ServiceError as exc:
        _raise_service_error(exc)
    return MediaRead.model_validate(media)


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media",
    responses=_ERRORS,
)
def delete_media(media_id: UUID, author: AuthorUser, session: DatabaseSession) -> Response:
    """Delete an owned image that is not attached to an article."""

    try:
        media_service.delete_media(session, media_id, author, _storage())
    except ServiceError as exc:
        _raise_service_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{media_id}/files/{variant}",
    summary="Deliver an image variant",
    responses=_ERRORS,
)
def deliver_media(
    media_id: UUID,
    variant: str,
    session: DatabaseSession,
    settings: SettingsDep,
    actor: OptionalUser,
) -> Response:
    """Serve a rendition. Published article images do not require authentication."""

    media = MediaRepository(session).get(media_id)
    rendition = None if media is None else media_service.variant_for(media, variant)
    if (
        media is None
        or rendition is None
        or not media_service.can_deliver(session, media, actor)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    storage = _storage()
    if settings.storage_provider == "s3":
        try:
            target = storage.get_url(rendition.storage_key)
        except StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Media not found."
            ) from exc
        return RedirectResponse(target, status_code=status.HTTP_302_FOUND)
    try:
        payload = storage.read(rendition.storage_key)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media not found."
        ) from exc
    cache = "public, max-age=86400" if actor is None else "private, max-age=300"
    return Response(
        content=payload,
        media_type=rendition.mime_type,
        headers={
            "Cache-Control": cache,
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{variant}{_extension(rendition.mime_type)}"',
        },
    )


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ServiceError("The file exceeds the upload size limit.", 413)
        chunks.append(chunk)
    if total == 0:
        raise ServiceError("The image is corrupted or is not a supported format.", 422)
    return b"".join(chunks)


def _extension(mime_type: str) -> str:
    return { "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp" }.get(
        mime_type, ""
    )
