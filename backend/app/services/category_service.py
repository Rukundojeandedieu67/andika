"""Global category management and hierarchy rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import MAX_CATEGORY_DEPTH, Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import (
    CategoryBrief,
    CategoryCreate,
    CategoryDetail,
    CategoryNode,
    CategoryUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.slug import slugify, with_suffix


def create_category(session: Session, payload: CategoryCreate) -> Category:
    """Create a platform category. Names are unique after case-folding."""

    categories = CategoryRepository(session)
    _ensure_name_available(categories, payload.name)
    parent = _parent_for_create(categories, payload.parent_id)
    category = Category(
        name=payload.name,
        name_key=payload.name.casefold(),
        slug=_allocate_slug(categories, payload.name),
        description=payload.description,
        parent_id=parent.id if parent is not None else None,
        is_active=payload.is_active,
    )
    return _save(session, categories, category)


def update_category(
    session: Session, category_id: uuid.UUID, payload: CategoryUpdate
) -> Category:
    """Change a category's name, description, or parent."""

    categories = CategoryRepository(session)
    category = _required(categories, category_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        _ensure_name_available(categories, changes["name"], excluding=category.id)
        category.name = changes["name"]
        category.name_key = changes["name"].casefold()
        category.slug = _allocate_slug(categories, changes["name"], excluding=category.id)
    if "description" in changes:
        category.description = changes["description"]
    if "parent_id" in changes:
        parent_id = changes["parent_id"]
        if parent_id is None:
            category.parent_id = None
        else:
            category.parent_id = _parent_for_move(categories, category, parent_id).id
    category.updated_at = datetime.now(UTC)
    return _save(session, categories, category)


def set_status(session: Session, category_id: uuid.UUID, *, is_active: bool) -> Category:
    """Activate or deactivate a category without changing its place in the tree."""

    categories = CategoryRepository(session)
    category = _required(categories, category_id)
    category.is_active = is_active
    category.updated_at = datetime.now(UTC)
    session.flush()
    return category


def delete_category(session: Session, category_id: uuid.UUID) -> None:
    """Delete a category. Articles keep their rows and lose this classification."""

    categories = CategoryRepository(session)
    category = _required(categories, category_id)
    if categories.list_children(category.id):
        raise ConflictError("Move or delete child categories first.")
    categories.delete(category)


def list_admin(
    session: Session, *, page: int, page_size: int
) -> tuple[list[Category], int]:
    """Return every category, including inactive ones, in name order."""

    return CategoryRepository(session).page(page=page, page_size=page_size)


def public_tree(session: Session) -> list[CategoryNode]:
    """Return active categories whose ancestors are also active."""

    categories = CategoryRepository(session)
    visible = [
        category
        for category in categories.list_all()
        if _is_public(category, categories)
    ]
    by_parent: dict[uuid.UUID | None, list[Category]] = {}
    for category in visible:
        parent_id = category.parent_id if _has_visible_parent(category, visible) else None
        if category.parent_id is not None and parent_id is None:
            continue
        by_parent.setdefault(parent_id, []).append(category)
    return [_node(category, by_parent) for category in by_parent.get(None, [])]


def get_public(session: Session, slug: str) -> CategoryDetail:
    """Return one publicly visible category, its parent, and its visible children."""

    categories = CategoryRepository(session)
    category = categories.get_by_slug(slug)
    if category is None or not _is_public(category, categories):
        raise NotFoundError("Category not found.")
    parent = categories.get(category.parent_id) if category.parent_id else None
    children = [
        child
        for child in categories.list_children(category.id)
        if _is_public(child, categories)
    ]
    return CategoryDetail(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        is_active=category.is_active,
        parent=None if parent is None else CategoryBrief.model_validate(parent),
        children=[CategoryBrief.model_validate(child) for child in children],
    )


def public_category_ids(session: Session, slug: str) -> list[uuid.UUID]:
    """Return a visible category and its visible descendants, or an empty list."""

    categories = CategoryRepository(session)
    category = categories.get_by_slug(slug)
    if category is None or not _is_public(category, categories):
        return []
    collected: list[uuid.UUID] = []
    pending = [category]
    seen: set[uuid.UUID] = set()
    while pending:
        current = pending.pop()
        if current.id in seen or not _is_public(current, categories):
            continue
        seen.add(current.id)
        collected.append(current.id)
        pending.extend(categories.list_children(current.id))
    return collected


def require_assignable(session: Session, category_id: uuid.UUID) -> Category:
    """Return a category that can be selected for an article."""

    categories = CategoryRepository(session)
    category = categories.get(category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    if not _is_public(category, categories):
        raise ServiceError("That category is not available.", 422)
    return category


def _required(categories: CategoryRepository, category_id: uuid.UUID) -> Category:
    category = categories.get(category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    return category


def _ensure_name_available(
    categories: CategoryRepository, name: str, *, excluding: uuid.UUID | None = None
) -> None:
    existing = categories.get_by_name_key(name.casefold())
    if existing is not None and existing.id != excluding:
        raise ConflictError("That category already exists.")


def _parent_for_create(
    categories: CategoryRepository, parent_id: uuid.UUID | None
) -> Category | None:
    if parent_id is None:
        return None
    parent = categories.get(parent_id)
    if parent is None:
        raise NotFoundError("Parent category not found.")
    if _depth(categories, parent) >= MAX_CATEGORY_DEPTH:
        raise ConflictError("Categories can be nested at most 3 levels.")
    return parent


def _parent_for_move(
    categories: CategoryRepository, category: Category, parent_id: uuid.UUID
) -> Category:
    if parent_id == category.id:
        raise ConflictError("A category cannot be its own parent.")
    parent = categories.get(parent_id)
    if parent is None:
        raise NotFoundError("Parent category not found.")
    if _is_descendant(categories, category.id, parent):
        raise ConflictError("A category cannot be moved under its own child.")
    new_depth = _depth(categories, parent) + 1
    if new_depth + _height(categories, category.id) - 1 > MAX_CATEGORY_DEPTH:
        raise ConflictError("Categories can be nested at most 3 levels.")
    return parent


def _depth(categories: CategoryRepository, category: Category) -> int:
    depth = 1
    seen = {category.id}
    parent_id = category.parent_id
    while parent_id is not None:
        if parent_id in seen:
            raise ConflictError("Category hierarchy contains a cycle.")
        seen.add(parent_id)
        parent = categories.get(parent_id)
        if parent is None:
            break
        depth += 1
        parent_id = parent.parent_id
    return depth


def _height(categories: CategoryRepository, category_id: uuid.UUID) -> int:
    children = categories.list_children(category_id)
    if not children:
        return 1
    return 1 + max(_height(categories, child.id) for child in children)


def _is_descendant(
    categories: CategoryRepository, ancestor_id: uuid.UUID, category: Category
) -> bool:
    seen: set[uuid.UUID] = set()
    current: Category | None = category
    while current is not None:
        if current.id in seen:
            return False
        if current.id == ancestor_id:
            return True
        seen.add(current.id)
        if current.parent_id is None:
            return False
        current = categories.get(current.parent_id)
    return False


def _is_public(category: Category, categories: CategoryRepository) -> bool:
    seen: set[uuid.UUID] = set()
    current: Category | None = category
    while current is not None:
        if current.id in seen or not current.is_active:
            return False
        seen.add(current.id)
        if current.parent_id is None:
            return True
        current = categories.get(current.parent_id)
    return False


def _has_visible_parent(category: Category, visible: list[Category]) -> bool:
    return any(item.id == category.parent_id for item in visible)


def _node(category: Category, by_parent: dict[uuid.UUID | None, list[Category]]) -> CategoryNode:
    children = by_parent.get(category.id, [])
    return CategoryNode(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        children=[_node(child, by_parent) for child in children],
    )


def _allocate_slug(
    categories: CategoryRepository, name: str, *, excluding: uuid.UUID | None = None
) -> str:
    base = slugify(name, fallback="category")
    candidate = base
    number = 2
    while categories.slug_in_use(candidate, excluding=excluding):
        candidate = with_suffix(base, number)
        number += 1
        if number > 100:
            raise ConflictError("A unique category slug could not be created.")
    return candidate


def _save(session: Session, categories: CategoryRepository, category: Category) -> Category:
    try:
        if category in session:
            session.flush()
            return category
        return categories.add(category)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That category already exists.") from exc
