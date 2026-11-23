"""Article and slug-redirect persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, false, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.editorial import EditorialStatus
from app.models.media import Media
from app.models.post import Post, PostRedirect, PostStatus
from app.models.publication import Publication, PublicationStatus, PublicationVisibility
from app.models.tag import Tag
from app.schemas.post import PostListParams


class PostRepository:
    """Read and write articles without applying permission rules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, post: Post) -> Post:
        self.session.add(post)
        self.session.flush()
        return post

    def get(self, post_id: uuid.UUID, *, lock: bool = False) -> Post | None:
        statement = select(Post).where(Post.id == post_id)
        if lock and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> Post | None:
        return self.session.scalar(
            select(Post)
            .options(
                joinedload(Post.author),
                joinedload(Post.category),
                selectinload(Post.tags),
                selectinload(Post.featured_media).selectinload(Media.variants),
            )
            .where(Post.slug == slug)
        )

    def get_redirect(self, slug: str) -> PostRedirect | None:
        return self.session.scalar(
            select(PostRedirect).where(PostRedirect.slug == slug)
        )

    def slug_in_use(self, slug: str, *, excluding: uuid.UUID | None = None) -> bool:
        post_id = self.session.scalar(select(Post.id).where(Post.slug == slug))
        if post_id is not None and post_id != excluding:
            return True
        redirect_id = self.session.scalar(
            select(PostRedirect.id).where(PostRedirect.slug == slug)
        )
        return redirect_id is not None

    def add_redirect(self, redirect: PostRedirect) -> PostRedirect:
        self.session.add(redirect)
        self.session.flush()
        return redirect

    def delete_redirect(self, redirect: PostRedirect) -> None:
        self.session.delete(redirect)
        self.session.flush()

    def list_public(self, params: PostListParams) -> tuple[list[Post], int]:
        clauses = [
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            self._public_publication_clause(),
            *self._common_clauses(params),
        ]
        return self._page(clauses, params, Post.published_at.desc(), Post.id.desc())

    def list_for_publication(
        self, publication_id: uuid.UUID, params: PostListParams
    ) -> tuple[list[Post], int]:
        clauses = [
            Post.publication_id == publication_id,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            *self._common_clauses(params),
        ]
        return self._page(clauses, params, Post.published_at.desc(), Post.id.desc())

    def list_editorial(
        self,
        publication_id: uuid.UUID,
        params: PostListParams,
        *,
        author_id: uuid.UUID | None,
        statuses: list[EditorialStatus] | None,
    ) -> tuple[list[Post], int]:
        clauses: list[ColumnElement[bool]] = [
            Post.publication_id == publication_id,
            Post.deleted_at.is_(None),
            *self._common_clauses(params),
        ]
        if author_id is not None:
            clauses.append(Post.author_id == author_id)
        if statuses:
            clauses.append(Post.editorial_status.in_(statuses))
        return self._page(clauses, params, Post.updated_at.desc(), Post.id.desc())

    def list_for_author(
        self, author_id: uuid.UUID, params: PostListParams
    ) -> tuple[list[Post], int]:
        clauses = [
            Post.author_id == author_id,
            Post.deleted_at.is_(None),
            *self._common_clauses(params),
        ]
        return self._page(clauses, params, Post.updated_at.desc(), Post.id.desc())

    def list_all(self, params: PostListParams) -> tuple[list[Post], int]:
        clauses: list[ColumnElement[bool]] = [Post.deleted_at.is_(None)]
        if params.status is not None:
            clauses.append(Post.status == params.status)
        if params.published_from is not None:
            clauses.append(Post.published_at >= params.published_from)
        if params.published_to is not None:
            clauses.append(Post.published_at <= params.published_to)
        clauses.extend(self._common_clauses(params))
        return self._page(clauses, params, Post.updated_at.desc(), Post.id.desc())

    def _common_clauses(self, params: PostListParams) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = []
        if params.author_id is not None:
            clauses.append(Post.author_id == params.author_id)
        if params.featured is not None:
            clauses.append(Post.is_featured.is_(params.featured))
        if params.category:
            category_ids = self._category_filter_ids(params.category)
            clauses.append(Post.category_id.in_(category_ids) if category_ids else false())
        if params.tag:
            clauses.append(Post.tags.any(Tag.slug == params.tag))
        if params.search:
            term = (
                params.search.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{term}%"
            clauses.append(
                or_(
                    Post.title.ilike(pattern, escape="\\"),
                    Post.content.ilike(pattern, escape="\\"),
                )
            )
        return clauses

    def _public_publication_clause(self) -> ColumnElement[bool]:
        visible = select(Publication.id).where(
            Publication.deleted_at.is_(None),
            Publication.status == PublicationStatus.ACTIVE,
            Publication.visibility == PublicationVisibility.PUBLIC,
        )
        return or_(Post.publication_id.is_(None), Post.publication_id.in_(visible))

    def _page(
        self,
        clauses: list[ColumnElement[bool]],
        params: PostListParams,
        *order: ColumnElement[object],
    ) -> tuple[list[Post], int]:
        total = self.session.scalar(select(func.count(Post.id)).where(*clauses))
        rows = (
            self.session.scalars(
                select(Post)
                .options(
                    joinedload(Post.author),
                    joinedload(Post.category),
                    selectinload(Post.tags),
                    selectinload(Post.featured_media).selectinload(Media.variants),
                )
                .where(*clauses)
                .order_by(*order)
                .offset((params.page - 1) * params.page_size)
                .limit(params.page_size)
            )
            .unique()
            .all()
        )
        return list(rows), int(total or 0)

    def _category_filter_ids(self, slug: str) -> list[uuid.UUID]:
        from app.services.category_service import public_category_ids

        return public_category_ids(self.session, slug)
