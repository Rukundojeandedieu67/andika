"""Public search queries. Ranking stays in SQL on PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, delete, func, literal_column, or_, select, text
from sqlalchemy.orm import Session, defer, joinedload, selectinload

from app.models.article_view import ArticleView
from app.models.category import Category
from app.models.comment import Comment, CommentStatus
from app.models.post import Post, PostStatus
from app.models.publication import Publication, PublicationStatus, PublicationVisibility
from app.models.search_event import SearchEvent
from app.models.tag import Tag, post_tags
from app.models.user import User
from app.services.search_text import document_matches, portable_score

_TRENDING_DAYS = 7
_COMMENT_WEIGHT = 3
_CARD_OPTIONS = (
    defer(Post.content),
    joinedload(Post.author),
    joinedload(Post.category),
    joinedload(Post.publication),
    selectinload(Post.tags),
)


class SearchRepository:
    """Read public discovery data without applying write rules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def page_articles(
        self,
        *,
        query: str,
        page: int,
        page_size: int,
        sort: str,
        category: str | None,
        tag: str | None,
        author: str | None,
        publication: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        featured_only: bool = False,
        feed: str | None = None,
    ) -> tuple[list[Post], int]:
        clauses = self._article_filters(
            category=category,
            tag=tag,
            author=author,
            publication=publication,
            date_from=date_from,
            date_to=date_to,
            featured_only=featured_only,
        )
        if query and self._postgres:
            return self._page_postgres(clauses, query, page, page_size, sort, feed)
        if query:
            return self._page_portable(clauses, query, page, page_size, sort, feed)
        return self._page_sql(clauses, page, page_size, sort, feed, rank=None)

    def counts_for(
        self, post_ids: list[uuid.UUID]
    ) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        if not post_ids:
            return {}, {}
        views = dict(
            self.session.execute(
                select(ArticleView.post_id, func.count(ArticleView.id))
                .where(ArticleView.post_id.in_(post_ids))
                .group_by(ArticleView.post_id)
            ).all()
        )
        comments = dict(
            self.session.execute(
                select(Comment.post_id, func.count(Comment.id))
                .where(
                    Comment.post_id.in_(post_ids),
                    Comment.deleted_at.is_(None),
                    Comment.status == CommentStatus.APPROVED,
                )
                .group_by(Comment.post_id)
            ).all()
        )
        return (
            {key: int(value) for key, value in views.items()},
            {key: int(value) for key, value in comments.items()},
        )

    def page_authors(
        self, *, query: str, page: int, page_size: int, category: str | None
    ) -> tuple[list[tuple[User, int]], int]:
        article_count = self._author_article_count()
        clauses: list[ColumnElement[bool]] = [article_count > 0]
        if category:
            clauses.append(self._author_in_category(category))
        if query:
            clauses.append(self._person_match(query))
        total = self.session.scalar(select(func.count(User.id)).where(*clauses))
        order = [article_count.desc(), User.username.asc()]
        if query and self._trgm:
            order.insert(0, self._person_similarity(query).desc())
        rows = self.session.execute(
            select(User, article_count)
            .where(*clauses)
            .order_by(*order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(user, int(count)) for user, count in rows], int(total or 0)

    def author_categories(self, author_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        if not author_ids:
            return {}
        rows = self.session.execute(
            select(Post.author_id, Category.name)
            .join(Category, Category.id == Post.category_id)
            .where(
                Post.author_id.in_(author_ids),
                *self._public_clauses(),
                Category.is_active.is_(True),
            )
            .distinct()
        ).all()
        grouped: dict[uuid.UUID, list[str]] = {}
        for author_id, name in rows:
            names = grouped.setdefault(author_id, [])
            if name not in names and len(names) < 3:
                names.append(name)
        return grouped

    def page_publications(
        self, *, query: str, page: int, page_size: int
    ) -> tuple[list[tuple[Publication, int]], int]:
        article_count = self._publication_article_count()
        clauses: list[ColumnElement[bool]] = [
            Publication.deleted_at.is_(None),
            Publication.status == PublicationStatus.ACTIVE,
            Publication.visibility == PublicationVisibility.PUBLIC,
            article_count > 0,
        ]
        if query:
            clauses.append(self._publication_match(query))
        total = self.session.scalar(select(func.count(Publication.id)).where(*clauses))
        order = [article_count.desc(), Publication.name.asc()]
        if query and self._trgm:
            order.insert(0, func.similarity(Publication.name, query).desc())
        rows = self.session.execute(
            select(Publication, article_count)
            .where(*clauses)
            .order_by(*order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(item, int(count)) for item, count in rows], int(total or 0)

    def publication_topics(
        self, publication_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[list[str], list[str]]]:
        if not publication_ids:
            return {}
        categories = self.session.execute(
            select(Post.publication_id, Category.name)
            .join(Category, Category.id == Post.category_id)
            .where(
                Post.publication_id.in_(publication_ids),
                *self._public_clauses(),
                Category.is_active.is_(True),
            )
            .distinct()
        ).all()
        tags = self.session.execute(
            select(Post.publication_id, Tag.name)
            .join(Post.tags)
            .where(Post.publication_id.in_(publication_ids), *self._public_clauses())
            .distinct()
        ).all()
        grouped: dict[uuid.UUID, tuple[list[str], list[str]]] = {
            publication_id: ([], []) for publication_id in publication_ids
        }
        for publication_id, name in categories:
            names, _tags = grouped[publication_id]
            if name not in names and len(names) < 3:
                names.append(name)
        for publication_id, name in tags:
            _names, tag_names = grouped[publication_id]
            if name not in tag_names and len(tag_names) < 3:
                tag_names.append(name)
        return grouped

    def page_categories(
        self, *, query: str, page: int, page_size: int
    ) -> tuple[list[tuple[Category, int]], int]:
        return self._page_taxonomy(Category, query, page, page_size, category=True)

    def page_tags(
        self, *, query: str, page: int, page_size: int
    ) -> tuple[list[tuple[Tag, int]], int]:
        return self._page_taxonomy(Tag, query, page, page_size, category=False)

    def related_candidates(self, post: Post, *, limit: int) -> list[Post]:
        overlap: list[ColumnElement[bool]] = [Post.author_id == post.author_id]
        if post.category_id is not None:
            overlap.append(Post.category_id == post.category_id)
        if post.publication_id is not None:
            overlap.append(Post.publication_id == post.publication_id)
        if post.tags:
            overlap.append(Post.tags.any(Tag.id.in_([tag.id for tag in post.tags])))
        rows = (
            self.session.scalars(
                select(Post)
                .options(*_CARD_OPTIONS)
                .where(Post.id != post.id, *self._public_clauses(), or_(*overlap))
                .order_by(Post.published_at.desc(), Post.id.asc())
                .limit(limit)
            )
            .unique()
            .all()
        )
        return list(rows)

    def suggestions(
        self, query: str, *, limit: int
    ) -> list[tuple[str, uuid.UUID, str, str | None]]:
        pattern = f"%{query.casefold()}%"
        prefix = f"{query.casefold()}%"
        title_match = func.lower(Post.title).like(pattern)
        if self._trgm:
            title_match = or_(title_match, func.similarity(Post.title, query) > 0.3)
        articles = self.session.execute(
            select(Post.id, Post.title, Post.slug)
            .where(*self._public_clauses(), title_match)
            .order_by(func.lower(Post.title).like(prefix).desc(), Post.published_at.desc())
            .limit(limit)
        ).all()
        authors = self.session.execute(
            select(User.id, User.username, User.full_name)
            .where(self._author_article_count() > 0, self._person_match(query))
            .order_by(User.username.asc())
            .limit(limit)
        ).all()
        publications = self.session.execute(
            select(Publication.id, Publication.name, Publication.slug)
            .where(
                Publication.deleted_at.is_(None),
                Publication.status == PublicationStatus.ACTIVE,
                Publication.visibility == PublicationVisibility.PUBLIC,
                func.lower(Publication.name).like(pattern),
            )
            .order_by(Publication.name.asc())
            .limit(limit)
        ).all()
        categories = self.session.execute(
            select(Category.id, Category.name, Category.slug)
            .where(Category.is_active.is_(True), func.lower(Category.name).like(pattern))
            .order_by(Category.name.asc())
            .limit(limit)
        ).all()
        tags = self.session.execute(
            select(Tag.id, Tag.name, Tag.slug)
            .where(self._tag_is_public(), func.lower(Tag.name).like(pattern))
            .order_by(Tag.name.asc())
            .limit(limit)
        ).all()
        found: list[tuple[str, uuid.UUID, str, str | None]] = []
        for post_id, title, slug in articles:
            found.append(("article", post_id, title, slug))
        for user_id, username, full_name in authors:
            found.append(("author", user_id, full_name or username, username))
        for publication_id, name, slug in publications:
            found.append(("publication", publication_id, name, slug))
        for category_id, name, slug in categories:
            found.append(("category", category_id, name, slug))
        for tag_id, name, slug in tags:
            found.append(("tag", tag_id, name, slug))
        return found[:limit]

    def record_search(
        self, *, query: str, search_type: str, result_count: int, retention_days: int
    ) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        self.session.execute(delete(SearchEvent).where(SearchEvent.created_at < cutoff))
        self.session.add(
            SearchEvent(query=query[:200], search_type=search_type, result_count=result_count)
        )
        self.session.flush()

    def stats_since(
        self, since: datetime
    ) -> tuple[int, list[tuple[str, int]], list[tuple[str, int]]]:
        total = self.session.scalar(
            select(func.count(SearchEvent.id)).where(SearchEvent.created_at >= since)
        )
        by_type = self.session.execute(
            select(SearchEvent.search_type, func.count(SearchEvent.id))
            .where(SearchEvent.created_at >= since)
            .group_by(SearchEvent.search_type)
            .order_by(func.count(SearchEvent.id).desc())
        ).all()
        top = self.session.execute(
            select(SearchEvent.query, func.count(SearchEvent.id))
            .where(SearchEvent.created_at >= since)
            .group_by(SearchEvent.query)
            .order_by(func.count(SearchEvent.id).desc(), SearchEvent.query.asc())
            .limit(10)
        ).all()
        return (
            int(total or 0),
            [(str(kind), int(count)) for kind, count in by_type],
            [(str(text), int(count)) for text, count in top],
        )

    @property
    def _postgres(self) -> bool:
        return self.session.get_bind().dialect.name == "postgresql"

    @property
    def _trgm(self) -> bool:
        if not self._postgres:
            return False
        cached = getattr(self, "_trgm_enabled", None)
        if cached is None:
            cached = bool(
                self.session.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")
                )
            )
            self._trgm_enabled = cached
        return bool(cached)

    def _public_clauses(self) -> list[ColumnElement[bool]]:
        visible = select(Publication.id).where(
            Publication.deleted_at.is_(None),
            Publication.status == PublicationStatus.ACTIVE,
            Publication.visibility == PublicationVisibility.PUBLIC,
        )
        return [
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
            or_(Post.publication_id.is_(None), Post.publication_id.in_(visible)),
        ]

    def _article_filters(
        self,
        *,
        category: str | None,
        tag: str | None,
        author: str | None,
        publication: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        featured_only: bool,
    ) -> list[ColumnElement[bool]]:
        clauses = self._public_clauses()
        if featured_only:
            clauses.append(Post.is_featured.is_(True))
        if category:
            from app.services.category_service import public_category_ids

            identifiers = public_category_ids(self.session, category)
            clauses.append(Post.category_id.in_(identifiers) if identifiers else Post.id.is_(None))
        if tag:
            clauses.append(Post.tags.any(Tag.slug == tag))
        if author:
            clauses.append(Post.author.has(User.username_key == author.casefold()))
        if publication:
            clauses.append(Post.publication.has(Publication.slug == publication))
        if date_from is not None:
            clauses.append(Post.published_at >= date_from)
        if date_to is not None:
            clauses.append(Post.published_at <= date_to)
        return clauses

    def _page_sql(
        self,
        clauses: list[ColumnElement[bool]],
        page: int,
        page_size: int,
        sort: str,
        feed: str | None,
        rank,
    ) -> tuple[list[Post], int]:
        total = self.session.scalar(select(func.count(Post.id)).where(*clauses))
        rows = (
            self.session.scalars(
                select(Post)
                .options(*_CARD_OPTIONS)
                .where(*clauses)
                .order_by(*self._order(sort, feed, rank))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return list(rows), int(total or 0)

    def _page_postgres(
        self,
        clauses: list[ColumnElement[bool]],
        query: str,
        page: int,
        page_size: int,
        sort: str,
        feed: str | None,
    ) -> tuple[list[Post], int]:
        vector = literal_column("posts.search_vector")
        tsquery = func.websearch_to_tsquery("simple", query)
        matched = or_(vector.op("@@")(tsquery), Post.title.ilike(_contains(query), escape="\\"))
        if self._trgm:
            matched = or_(matched, func.similarity(Post.title, query) > 0.3)
        return self._page_sql(
            [*clauses, matched],
            page,
            page_size,
            sort,
            feed,
            func.ts_rank_cd(vector, tsquery),
        )

    def _page_portable(
        self,
        clauses: list[ColumnElement[bool]],
        query: str,
        page: int,
        page_size: int,
        sort: str,
        feed: str | None,
    ) -> tuple[list[Post], int]:
        rows = self.session.execute(
            select(Post.id, Post.title, Post.search_document, Post.published_at).where(*clauses)
        ).all()
        matched = [row for row in rows if document_matches(row.search_document or "", query)]
        views, comments = self.counts_for([row.id for row in matched])

        def sort_key(row) -> tuple:
            published = row.published_at or datetime.min.replace(tzinfo=UTC)
            if feed == "popular" or sort == "most_viewed":
                return (-views.get(row.id, 0), _reverse_time(published), str(row.id))
            if feed == "discussed" or sort == "most_commented":
                return (-comments.get(row.id, 0), _reverse_time(published), str(row.id))
            if feed == "trending":
                score = _trending(views.get(row.id, 0), comments.get(row.id, 0), published)
                return (-score, _reverse_time(published), str(row.id))
            if sort == "oldest":
                return (published, str(row.id))
            if sort == "relevance":
                score = portable_score(row.title, row.search_document or "", query)
                return (-score, _reverse_time(published), str(row.id))
            return (_reverse_time(published), str(row.id))

        matched.sort(key=sort_key)
        chosen = matched[(page - 1) * page_size : page * page_size]
        return self._load_in_order([row.id for row in chosen]), len(matched)

    def _load_in_order(self, post_ids: list[uuid.UUID]) -> list[Post]:
        if not post_ids:
            return []
        posts = (
            self.session.scalars(
                select(Post).options(*_CARD_OPTIONS).where(Post.id.in_(post_ids))
            )
            .unique()
            .all()
        )
        by_id = {post.id: post for post in posts}
        return [by_id[post_id] for post_id in post_ids if post_id in by_id]

    def _order(self, sort: str, feed: str | None, rank):
        if feed == "trending":
            return (self._trending_score().desc(), Post.published_at.desc(), Post.id.desc())
        if feed == "popular":
            return (self._view_count().desc(), Post.published_at.desc(), Post.id.desc())
        if feed == "discussed":
            return (self._comment_count().desc(), Post.published_at.desc(), Post.id.desc())
        if feed in {"latest", "featured"}:
            return (Post.published_at.desc(), Post.id.desc())
        if sort == "oldest":
            return (Post.published_at.asc(), Post.id.asc())
        if sort == "most_viewed":
            return (self._view_count().desc(), Post.published_at.desc(), Post.id.desc())
        if sort == "most_commented":
            return (self._comment_count().desc(), Post.published_at.desc(), Post.id.desc())
        if sort == "relevance" and rank is not None:
            return (rank.desc(), Post.published_at.desc(), Post.id.desc())
        return (Post.published_at.desc(), Post.id.desc())

    def _view_count(self):
        return (
            select(func.count(ArticleView.id))
            .where(ArticleView.post_id == Post.id)
            .correlate(Post)
            .scalar_subquery()
        )

    def _comment_count(self):
        return (
            select(func.count(Comment.id))
            .where(
                Comment.post_id == Post.id,
                Comment.deleted_at.is_(None),
                Comment.status == CommentStatus.APPROVED,
            )
            .correlate(Post)
            .scalar_subquery()
        )

    def _trending_score(self):
        cutoff = datetime.now(UTC) - timedelta(days=_TRENDING_DAYS)
        recent_views = (
            select(func.count(ArticleView.id))
            .where(ArticleView.post_id == Post.id, ArticleView.viewed_at >= cutoff)
            .correlate(Post)
            .scalar_subquery()
        )
        recent_comments = (
            select(func.count(Comment.id))
            .where(
                Comment.post_id == Post.id,
                Comment.deleted_at.is_(None),
                Comment.status == CommentStatus.APPROVED,
                Comment.created_at >= cutoff,
            )
            .correlate(Post)
            .scalar_subquery()
        )
        if self._postgres:
            age_days = func.extract("epoch", func.now() - Post.published_at) / 86400.0
        else:
            age_days = func.julianday("now") - func.julianday(Post.published_at)
        engagement = recent_views + (_COMMENT_WEIGHT * recent_comments)
        return engagement / (1.0 + func.coalesce(age_days, 0.0) / _TRENDING_DAYS)

    def _author_article_count(self):
        return (
            select(func.count(Post.id))
            .where(Post.author_id == User.id, *self._public_clauses())
            .correlate(User)
            .scalar_subquery()
        )

    def _author_in_category(self, slug: str):
        from app.services.category_service import public_category_ids

        identifiers = public_category_ids(self.session, slug)
        if not identifiers:
            return User.id.is_(None)
        return (
            select(Post.id)
            .where(
                Post.author_id == User.id,
                Post.category_id.in_(identifiers),
                *self._public_clauses(),
            )
            .correlate(User)
            .exists()
        )

    def _publication_article_count(self):
        return (
            select(func.count(Post.id))
            .where(Post.publication_id == Publication.id, *self._public_clauses())
            .correlate(Publication)
            .scalar_subquery()
        )

    def _page_taxonomy(self, model, query: str, page: int, page_size: int, *, category: bool):
        count = self._taxonomy_count(model, category=category)
        clauses: list[ColumnElement[bool]] = [count > 0]
        if category:
            clauses.append(model.is_active.is_(True))
        if query:
            clauses.append(func.lower(model.name).like(f"%{query.casefold()}%"))
        total = self.session.scalar(select(func.count(model.id)).where(*clauses))
        rows = self.session.execute(
            select(model, count)
            .where(*clauses)
            .order_by(count.desc(), model.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(item, int(value)) for item, value in rows], int(total or 0)

    def _taxonomy_count(self, model, *, category: bool):
        if category:
            return (
                select(func.count(Post.id))
                .where(Post.category_id == model.id, *self._public_clauses())
                .correlate(model)
                .scalar_subquery()
            )
        return (
            select(func.count(func.distinct(Post.id)))
            .select_from(Post)
            .join(post_tags, post_tags.c.post_id == Post.id)
            .where(post_tags.c.tag_id == model.id, *self._public_clauses())
            .correlate(model)
            .scalar_subquery()
        )

    def _tag_is_public(self):
        return (
            select(Post.id)
            .select_from(Post)
            .join(post_tags, post_tags.c.post_id == Post.id)
            .where(post_tags.c.tag_id == Tag.id, *self._public_clauses())
            .correlate(Tag)
            .exists()
        )

    def _person_match(self, query: str):
        pattern = f"%{query.casefold()}%"
        basic = or_(
            func.lower(User.username).like(pattern),
            func.lower(func.coalesce(User.full_name, "")).like(pattern),
        )
        if not self._trgm:
            return basic
        return or_(
            basic,
            func.similarity(User.username, query) > 0.3,
            func.similarity(func.coalesce(User.full_name, ""), query) > 0.3,
        )

    def _person_similarity(self, query: str):
        return func.greatest(
            func.similarity(User.username, query),
            func.similarity(func.coalesce(User.full_name, ""), query),
        )

    def _publication_match(self, query: str):
        pattern = f"%{query.casefold()}%"
        basic = or_(
            func.lower(Publication.name).like(pattern),
            func.lower(func.coalesce(Publication.description, "")).like(pattern),
        )
        if not self._trgm:
            return basic
        return or_(basic, func.similarity(Publication.name, query) > 0.3)


def _reverse_time(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return -value.timestamp()


def _trending(views: int, comments: int, published_at: datetime) -> float:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age_days = max(0.0, (datetime.now(UTC) - published_at).total_seconds() / 86400.0)
    return (views + _COMMENT_WEIGHT * comments) / (1.0 + age_days / _TRENDING_DAYS)


def _contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
