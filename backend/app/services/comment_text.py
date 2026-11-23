"""Plain-text rules for comment bodies."""

from __future__ import annotations

import re

_TAGS = re.compile(r"<[^>]*>")


def normalize_comment_body(value: str, *, max_length: int) -> str:
    """Collapse whitespace and drop HTML tags. The stored text is plain text."""

    cleaned = " ".join(_TAGS.sub("", value).split())
    if cleaned == "":
        raise ValueError("Comment cannot be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"Comment must be at most {max_length} characters.")
    return cleaned
