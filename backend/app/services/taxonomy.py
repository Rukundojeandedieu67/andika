"""Shared name rules for categories and tags."""

from __future__ import annotations


def normalize_taxonomy_name(value: str) -> str:
    """Collapse whitespace. Uniqueness uses the case-folded form of this value."""

    cleaned = " ".join(value.split())
    if cleaned == "" or len(cleaned) > 80:
        raise ValueError("Name must be 1 to 80 characters.")
    return cleaned
