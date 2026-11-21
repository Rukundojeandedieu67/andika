"""Validate images and build aspect-preserving WebP variants."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError

from app.core.config import Settings
from app.services.exceptions import ServiceError

_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}
_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
}


@dataclass(frozen=True)
class EncodedImage:
    """Bytes for one rendition and the size it was saved at."""

    data: bytes
    width: int
    height: int
    mime_type: str
    extension: str


@dataclass(frozen=True)
class ProcessedImage:
    """The orientation-corrected original and three WebP derivatives."""

    original: EncodedImage
    large: EncodedImage
    medium: EncodedImage
    thumbnail: EncodedImage


def process_image(
    data: bytes, *, declared_mime: str | None, settings: Settings
) -> ProcessedImage:
    """Decode an upload, strip metadata, and build the standard variants."""

    if len(data) > settings.media_max_upload_bytes:
        raise ServiceError("The file exceeds the upload size limit.", 413)
    Image.MAX_IMAGE_PIXELS = settings.media_max_pixels
    try:
        with Image.open(BytesIO(data)) as probe:
            probe.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            detected = (image.format or "").upper()
            if detected not in _FORMATS:
                raise ServiceError(
                    "Only JPEG, PNG, and WebP images are accepted.", 422
                )
            mime_type, extension = _FORMATS[detected]
            _reject_spoofed_type(declared_mime, mime_type)
            if getattr(image, "n_frames", 1) > 1:
                raise ServiceError("Animated images are not supported.", 422)
            oriented = ImageOps.exif_transpose(image)
            if oriented is None:
                raise ServiceError("The image is corrupted or is not a supported format.", 422)
            _reject_oversized(oriented, settings)
            original = _encode_original(oriented, detected, mime_type, extension, settings)
            return ProcessedImage(
                original=original,
                large=_encode_webp(oriented, settings.media_large_edge, settings),
                medium=_encode_webp(oriented, settings.media_medium_edge, settings),
                thumbnail=_encode_webp(oriented, settings.media_thumbnail_edge, settings),
            )
    except ServiceError:
        raise
    except (DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ServiceError(
            "The image is corrupted or is not a supported format.", 422
        ) from exc


def _reject_spoofed_type(declared_mime: str | None, detected_mime: str) -> None:
    if declared_mime is None:
        return
    declared = declared_mime.split(";", 1)[0].strip().lower()
    declared = _MIME_ALIASES.get(declared, declared)
    if declared in {"", "application/octet-stream"}:
        return
    if declared != detected_mime:
        raise ServiceError("The file content does not match its declared type.", 422)


def _reject_oversized(image: Image.Image, settings: Settings) -> None:
    if (
        image.width > settings.media_max_dimension
        or image.height > settings.media_max_dimension
        or image.width * image.height > settings.media_max_pixels
    ):
        raise ServiceError("The image exceeds the maximum dimensions.", 422)


def _encode_original(
    image: Image.Image,
    image_format: str,
    mime_type: str,
    extension: str,
    settings: Settings,
) -> EncodedImage:
    prepared = image
    save_format = image_format
    options: dict[str, object] = {}
    if image_format == "JPEG":
        prepared = _flatten(image)
        options = {"quality": 90, "optimize": True}
    elif image_format == "PNG":
        options = {"optimize": True}
    else:
        prepared = image.convert("RGBA") if "A" in image.getbands() else _flatten(image)
        options = {"quality": settings.media_webp_quality, "method": 4}
        save_format = "WEBP"
    return _save(prepared, save_format, mime_type, extension, options)


def _encode_webp(image: Image.Image, edge: int, settings: Settings) -> EncodedImage:
    fitted = _fit(image, edge)
    prepared = fitted.convert("RGBA") if "A" in fitted.getbands() else _flatten(fitted)
    return _save(
        prepared,
        "WEBP",
        "image/webp",
        ".webp",
        {"quality": settings.media_webp_quality, "method": 4},
    )


def _fit(image: Image.Image, edge: int) -> Image.Image:
    """Shrink an image so both sides fit inside `edge`. Small images stay as they are."""

    if image.width <= edge and image.height <= edge:
        return image.copy()
    fitted = image.copy()
    fitted.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    return fitted


def _flatten(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if "A" in image.getbands():
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")


def _save(
    image: Image.Image,
    image_format: str,
    mime_type: str,
    extension: str,
    options: dict[str, object],
) -> EncodedImage:
    buffer = BytesIO()
    image.save(buffer, format=image_format, **options)
    return EncodedImage(
        data=buffer.getvalue(),
        width=image.width,
        height=image.height,
        mime_type=mime_type,
        extension=extension,
    )
