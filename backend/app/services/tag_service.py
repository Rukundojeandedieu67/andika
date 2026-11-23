"""Reusable tag management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.repositories.tag_repository import TagRepository
from app.schemas.tag import TagCreate, TagUpdate
from app.services.exceptions import ConflictError, NotFoundError
from app.services.search_text import refresh_for_tag
from app.services.slug import slugify, with_suffix


def create_tag(session: Session, payload: TagCreate) -> Tag:
    """Create a tag that any author can reuse. Matching names are rejected."""

    tags = TagRepository(session)
    _ensure_name_available(tags, payload.name)
    tag = Tag(
        name=payload.name,
        name_key=payload.name.casefold(),
        slug=_allocate_slug(tags, payload.name),
        description=payload.description,
    )
    return _save(session, tags, tag)


def update_tag(session: Session, tag_id: uuid.UUID, payload: TagUpdate) -> Tag:
    """Change a tag's display name or description."""

    tags = TagRepository(session)
    tag = tags.get(tag_id)
    if tag is None:
        raise NotFoundError("Tag not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        _ensure_name_available(tags, changes["name"], excluding=tag.id)
        tag.name = changes["name"]
        tag.name_key = changes["name"].casefold()
        tag.slug = _allocate_slug(tags, changes["name"], excluding=tag.id)
    if "description" in changes:
        tag.description = changes["description"]
    tag.updated_at = datetime.now(UTC)
    saved = _save(session, tags, tag)
    if "name" in changes and changes["name"] is not None:
        refresh_for_tag(session, saved.id)
    return saved


def delete_tag(session: Session, tag_id: uuid.UUID) -> None:
    """Delete a tag and its article associations. Articles themselves remain."""

    tags = TagRepository(session)
    tag = tags.get(tag_id)
    if tag is None:
        raise NotFoundError("Tag not found.")
    tags.delete(tag)


def list_public(session: Session, *, page: int, page_size: int) -> tuple[list[Tag], int]:
    """Return tags that appear on at least one published article."""

    return TagRepository(session).page_public(page=page, page_size=page_size)


def list_all(session: Session, *, page: int, page_size: int) -> tuple[list[Tag], int]:
    """Return every tag, including tags that are not used publicly yet."""

    return TagRepository(session).page_all(page=page, page_size=page_size)


def get_public(session: Session, slug: str) -> Tag:
    """Return a tag that is used by a published article."""

    tags = TagRepository(session)
    tag = tags.get_by_slug(slug)
    if tag is None or not tags.is_public(tag.id):
        raise NotFoundError("Tag not found.")
    return tag


def require_tags(session: Session, tag_ids: list[uuid.UUID]) -> list[Tag]:
    """Return the requested tags in the caller's order, without duplicates."""

    unique_ids = list(dict.fromkeys(tag_ids))
    tags = TagRepository(session).get_many(unique_ids)
    found = {tag.id: tag for tag in tags}
    if len(found) != len(unique_ids):
        raise NotFoundError("One or more tags do not exist.")
    return [found[tag_id] for tag_id in unique_ids]


def _ensure_name_available(
    tags: TagRepository, name: str, *, excluding: uuid.UUID | None = None
) -> None:
    existing = tags.get_by_name_key(name.casefold())
    if existing is not None and existing.id != excluding:
        raise ConflictError("That tag already exists.")


def _allocate_slug(tags: TagRepository, name: str, *, excluding: uuid.UUID | None = None) -> str:
    base = slugify(name, fallback="tag")
    candidate = base
    number = 2
    while tags.slug_in_use(candidate, excluding=excluding):
        candidate = with_suffix(base, number)
        number += 1
        if number > 100:
            raise ConflictError("A unique tag slug could not be created.")
    return candidate


def _save(session: Session, tags: TagRepository, tag: Tag) -> Tag:
    try:
        if tag in session:
            session.flush()
            return tag
        return tags.add(tag)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That tag already exists.") from exc
