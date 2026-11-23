"""Article creation, publishing, and editing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.editorial import EditorialStatus
from app.models.post import Post, PostRedirect, PostStatus
from app.models.post_revision import PostRevision
from app.models.publication import MembershipRole, Publication
from app.models.user import User, UserRole
from app.repositories.post_repository import PostRepository
from app.schemas.post import PostCreate, PostListParams, PostUpdate
from app.services.category_service import require_assignable
from app.services.editorial_service import record_transition
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.post_revision_service import (
    get_revision,
    list_revisions,
    record_previous_content,
)
from app.services.publication_access import (
    EDITOR_ROLES,
    require_active_member,
    require_active_publication,
    require_editor,
    require_publication,
)
from app.services.search_text import assign_search_document
from app.services.slug import slugify, with_suffix
from app.services.tag_service import require_tags
from app.services.visibility import is_publicly_listed

_CONTENT_FIELDS = {"title", "excerpt", "content"}


def reading_time_minutes(content: str) -> int:
    """Estimate reading time from a 200-words-per-minute pace."""

    words = len(content.split())
    if words == 0:
        return 0
    return max(1, (words + 199) // 200)


def create_draft(session: Session, author: User, payload: PostCreate) -> Post:
    """Create a draft owned by the authenticated author."""

    if payload.author_id is not None:
        raise ServiceError("You do not have permission to perform this action.", 403)
    publication = _publication_for_new_article(session, author, payload.publication_id)
    posts = PostRepository(session)
    post = Post(
        author_id=author.id,
        publication_id=None if publication is None else publication.id,
        editorial_status=None if publication is None else EditorialStatus.DRAFT,
        title=payload.title,
        slug=_allocate_slug(posts, payload.title),
        subtitle=payload.subtitle,
        excerpt=payload.excerpt,
        content=payload.content,
        featured_image=payload.featured_image,
        status=PostStatus.DRAFT,
        is_featured=payload.is_featured,
        allow_comments=payload.allow_comments,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        reading_time=reading_time_minutes(payload.content),
    )
    _apply_featured(
        session,
        post,
        author,
        featured_image=payload.featured_image,
        featured_image_id=payload.featured_image_id,
        url_set=payload.featured_image is not None,
        media_set=payload.featured_image_id is not None,
    )
    _apply_taxonomy(
        session,
        post,
        category_id=payload.category_id,
        tag_ids=payload.tag_ids,
        category_set=True,
        tags_set=True,
    )
    post.author = author
    post.publication = publication
    assign_search_document(post)
    try:
        return posts.add(post)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That slug is already in use.") from exc


def list_published(session: Session, params: PostListParams) -> tuple[list[Post], int]:
    """Return one page of publicly visible articles."""

    return PostRepository(session).list_public(params)


def list_mine(
    session: Session, author: User, params: PostListParams
) -> tuple[list[Post], int]:
    """Return the caller's own articles, including drafts and archived ones."""

    return PostRepository(session).list_for_author(author.id, params)


def list_all(session: Session, params: PostListParams) -> tuple[list[Post], int]:
    """Return every article that has not been deleted."""

    return PostRepository(session).list_all(params)


def get_published_by_slug(session: Session, slug: str) -> Post | str:
    """Return a published article, or the current slug when an old slug was requested."""

    posts = PostRepository(session)
    post = posts.get_by_slug(slug)
    if is_publicly_listed(session, post):
        return post
    redirect = posts.get_redirect(slug)
    if redirect is None:
        raise NotFoundError()
    current = posts.get(redirect.post_id)
    if not is_publicly_listed(session, current):
        raise NotFoundError()
    return current.slug


def get_owned(session: Session, post_id: uuid.UUID, author: User) -> Post:
    """Return one of the caller's articles in any status."""

    post = PostRepository(session).get(post_id)
    if post is None or post.deleted_at is not None or post.author_id != author.id:
        raise NotFoundError()
    return post


def update_post(
    session: Session, post_id: uuid.UUID, actor: User, payload: PostUpdate
) -> Post:
    """Apply an edit and store the previous content when it changes."""

    post = get_editable_post(session, post_id, actor, lock=True)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return post
    if _CONTENT_FIELDS.intersection(changes):
        record_previous_content(session, post, actor)
    if "title" in changes and changes["title"] is not None:
        post.title = changes["title"]
    if "slug" in changes and changes["slug"] is not None:
        _assign_slug(session, post, changes["slug"])
    elif (
        "title" in changes
        and "slug" not in changes
        and post.status is PostStatus.DRAFT
        and post.published_at is None
    ):
        post.slug = _allocate_slug(
            PostRepository(session), post.title, excluding=post.id
        )
    for field in (
        "subtitle",
        "excerpt",
        "content",
        "is_featured",
        "allow_comments",
        "meta_title",
        "meta_description",
    ):
        if field in changes:
            setattr(post, field, changes[field])
    if "featured_image" in changes or "featured_image_id" in changes:
        _apply_featured(
            session,
            post,
            actor,
            featured_image=changes.get("featured_image"),
            featured_image_id=changes.get("featured_image_id"),
            url_set="featured_image" in changes,
            media_set="featured_image_id" in changes,
        )
    if "category_id" in changes or "tag_ids" in changes:
        _apply_taxonomy(
            session,
            post,
            category_id=changes.get("category_id"),
            tag_ids=changes.get("tag_ids"),
            category_set="category_id" in changes,
            tags_set="tag_ids" in changes,
        )
    post.reading_time = reading_time_minutes(post.content)
    post.updated_at = datetime.now(UTC)
    assign_search_document(post)
    _flush(session)
    return post


def publish_post(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    """Move a draft to the public state and record the publication time."""

    post = _existing_post(session, post_id, lock=True)
    if post.publication_id is None:
        _require_independent_editor(post, actor)
    else:
        _require_publication_publisher(session, post, actor)
    if post.status is not PostStatus.DRAFT:
        raise ConflictError("Only a draft can be published.")
    if post.content.strip() == "":
        raise ServiceError("Add article content before publishing.", 422)
    now = datetime.now(UTC)
    post.status = PostStatus.PUBLISHED
    post.published_at = now
    post.updated_at = now
    if post.publication_id is not None:
        previous = post.editorial_status
        post.editorial_status = EditorialStatus.PUBLISHED
        record_transition(
            session,
            post=post,
            actor=actor,
            action="publish",
            from_status=previous,
            to_status=EditorialStatus.PUBLISHED,
        )
    _flush(session)
    return post


def unpublish_post(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    """Return a published article to draft. It leaves public listings."""

    post = _existing_post(session, post_id, lock=True)
    _require_unpublish(session, post, actor)
    if post.status is not PostStatus.PUBLISHED:
        raise ConflictError("Only a published article can be unpublished.")
    previous = post.editorial_status
    post.status = PostStatus.DRAFT
    post.published_at = None
    post.updated_at = datetime.now(UTC)
    if post.publication_id is not None:
        post.editorial_status = EditorialStatus.APPROVED
        record_transition(
            session,
            post=post,
            actor=actor,
            action="unpublish",
            from_status=previous,
            to_status=EditorialStatus.APPROVED,
        )
    _flush(session)
    return post


def archive_post(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    """Hide an article from the public without deleting it."""

    post = _existing_post(session, post_id, lock=True)
    _require_edit(session, post, actor)
    if post.status is PostStatus.ARCHIVED:
        raise ConflictError("That article is already archived.")
    now = datetime.now(UTC)
    post.status = PostStatus.ARCHIVED
    post.published_at = None
    post.updated_at = now
    if post.publication_id is not None and post.editorial_status is not None:
        record_transition(
            session,
            post=post,
            actor=actor,
            action="archive",
            from_status=post.editorial_status,
            to_status=post.editorial_status,
        )
    _flush(session)
    return post


def delete_post(session: Session, post_id: uuid.UUID, actor: User) -> None:
    """Soft-delete an article so it no longer appears in any listing."""

    post = get_editable_post(session, post_id, actor, lock=True)
    post.deleted_at = datetime.now(UTC)
    post.updated_at = post.deleted_at
    _flush(session)


def list_post_revisions(
    session: Session, post_id: uuid.UUID, actor: User
) -> list[PostRevision]:
    """Return revision history for an article the actor can edit."""

    get_editable_post(session, post_id, actor)
    return list_revisions(session, post_id)


def get_post_revision(
    session: Session,
    post_id: uuid.UUID,
    revision_id: uuid.UUID,
    actor: User,
) -> PostRevision:
    """Return one revision for an article the actor can edit."""

    get_editable_post(session, post_id, actor)
    return get_revision(session, post_id, revision_id)


def get_editable_post(
    session: Session, post_id: uuid.UUID, actor: User, *, lock: bool = False
) -> Post:
    """Return an article the actor is allowed to edit."""

    post = _existing_post(session, post_id, lock=lock)
    _require_edit(session, post, actor)
    return post


def _existing_post(session: Session, post_id: uuid.UUID, *, lock: bool) -> Post:
    post = PostRepository(session).get(post_id, lock=lock)
    if post is None or post.deleted_at is not None:
        raise NotFoundError()
    return post


def _publication_for_new_article(
    session: Session, author: User, publication_id: uuid.UUID | None
) -> Publication | None:
    if publication_id is None:
        if author.role not in {UserRole.AUTHOR, UserRole.ADMIN}:
            raise ServiceError("You do not have permission to perform this action.", 403)
        return None
    publication = require_publication(session, publication_id)
    require_active_publication(publication)
    require_active_member(session, publication, author)
    return publication


def _require_independent_editor(post: Post, actor: User) -> None:
    if actor.role is UserRole.ADMIN or post.author_id == actor.id:
        return
    raise NotFoundError()


def _require_edit(session: Session, post: Post, actor: User) -> None:
    if post.publication_id is None:
        _require_independent_editor(post, actor)
        return
    publication = require_publication(session, post.publication_id)
    membership = require_active_member(session, publication, actor)
    if membership.role in EDITOR_ROLES:
        return
    if post.author_id != actor.id:
        raise ServiceError("You can only edit your own articles in this publication.", 403)
    if post.status is not PostStatus.DRAFT:
        raise ServiceError("You can only edit your own drafts in this publication.", 403)
    if membership.role is MembershipRole.CONTRIBUTOR and post.editorial_status not in {
        EditorialStatus.DRAFT,
        EditorialStatus.CHANGES_REQUESTED,
    }:
        raise ServiceError(
            "Contributors can edit drafts and articles that need changes.", 403
        )


def _require_unpublish(session: Session, post: Post, actor: User) -> None:
    if post.publication_id is None:
        _require_independent_editor(post, actor)
        return
    publication = require_publication(session, post.publication_id)
    require_active_publication(publication)
    membership = require_active_member(session, publication, actor)
    require_editor(membership)


def _require_publication_publisher(session: Session, post: Post, actor: User) -> None:
    publication = require_publication(session, post.publication_id)  # type: ignore[arg-type]
    require_active_publication(publication)
    membership = require_active_member(session, publication, actor)
    if publication.requires_review:
        if membership.role not in EDITOR_ROLES:
            raise ServiceError("Publication articles are published by an editor.", 403)
        if post.editorial_status is not EditorialStatus.APPROVED:
            raise ConflictError("This article has not been approved for publication.")
        return
    if membership.role in EDITOR_ROLES:
        return
    if membership.role is MembershipRole.AUTHOR and post.author_id == actor.id:
        return
    raise ServiceError("You do not have permission to publish this article.", 403)


def _allocate_slug(
    posts: PostRepository, title: str, *, excluding: uuid.UUID | None = None
) -> str:
    base = slugify(title)
    candidate = base
    number = 2
    while posts.slug_in_use(candidate, excluding=excluding):
        candidate = with_suffix(base, number)
        number += 1
        if number > 1000:
            raise ConflictError("A unique slug could not be created.")
    return candidate


def _assign_slug(session: Session, post: Post, slug: str) -> None:
    if slug == post.slug:
        return
    posts = PostRepository(session)
    redirect = posts.get_redirect(slug)
    if redirect is not None and redirect.post_id == post.id:
        posts.delete_redirect(redirect)
    elif posts.slug_in_use(slug, excluding=post.id):
        raise ConflictError("That slug is already in use.")
    if post.status is PostStatus.PUBLISHED:
        posts.add_redirect(PostRedirect(post_id=post.id, slug=post.slug))
    post.slug = slug


def _flush(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That slug is already in use.") from exc


def _apply_featured(
    session: Session,
    post: Post,
    actor: User,
    *,
    featured_image: str | None,
    featured_image_id: uuid.UUID | None,
    url_set: bool,
    media_set: bool,
) -> None:
    from app.services.media_service import require_attachable, variant_url

    if media_set and featured_image_id is not None:
        media = require_attachable(session, featured_image_id, actor)
        post.featured_media = media
        post.featured_image = variant_url(media, "large")
        return
    if media_set:
        post.featured_media = None
        post.featured_image = featured_image if url_set else None
        return
    if url_set:
        post.featured_image = featured_image
        if featured_image is not None:
            post.featured_image_id = None


def _apply_taxonomy(
    session: Session,
    post: Post,
    *,
    category_id: uuid.UUID | None,
    tag_ids: list[uuid.UUID] | None,
    category_set: bool,
    tags_set: bool,
) -> None:
    if category_set:
        post.category = None if category_id is None else require_assignable(session, category_id)
    if tags_set:
        post.tags = [] if not tag_ids else require_tags(session, tag_ids)
