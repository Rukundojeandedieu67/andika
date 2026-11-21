"""URL slug generation for articles."""

from __future__ import annotations

import re
import unicodedata

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_REPEATED_DASH = re.compile(r"-{2,}")
_RESERVED = {"mine", "admin"}
_MAX_LENGTH = 120


def slugify(title: str, *, fallback: str = "article") -> str:
    """Turn a title into a lowercase URL slug."""

    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _REPEATED_DASH.sub("-", _NON_SLUG.sub("-", ascii_text)).strip("-")
    slug = slug[:_MAX_LENGTH].strip("-")
    if slug == "" or slug in _RESERVED:
        return fallback
    return slug


def with_suffix(base: str, number: int) -> str:
    """Append a numeric suffix without exceeding the slug length."""

    suffix = f"-{number}"
    trimmed = base[: _MAX_LENGTH - len(suffix)].strip("-")
    if trimmed == "":
        trimmed = "article"
    return f"{trimmed}{suffix}"
