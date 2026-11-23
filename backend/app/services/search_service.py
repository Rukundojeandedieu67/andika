"""Search, discovery, related articles, suggestions, and view counting."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import Settings
from app.core.rate_limit import limit_suggestions
from app.models.post import Post
from app.models.user import User
from app.repositories.search_repository import SearchRepository
from app.schemas.category import CategoryBrief
from app.schemas.post import AuthorPublic
from app.schemas.search import (
    ArticleCard,
    ArticleCardPage,
    AuthorCard,
    AuthorCardPage,
    PublicationBrief,
    PublicationCard,
    PublicationCardPage,
    QueryCount,
    SearchResponse,
    SearchStats,
    Suggestion,
    SuggestionList,
    TaxonomyCard,
    TaxonomyCardPage,
    TypeCount,
)
from app.schemas.tag import TagBrief
from app.services.exceptions import NotFoundError, ServiceError
from app.services.post_service import get_published_by_slug
from app.services.search_text import plain
from app.services.visibility import is_publicly_listed

_WORDS = re.compile(r"\w", re.UNICODE)
_VISITOR = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_SOURCE = re.compile(r"^[a-z0-9_-]{1,40}$")
_TITLE_WORD = re.compile(r"\w{4,}", re.UNICODE)
_HEALTH_AGENTS = ("health-check", "kube-probe")
_RETENTION_DAYS = 90
_STATS_DAYS = 30
_RELATED_CANDIDATES = 100
_SECTIONS = ("articles", "authors", "publications", "categories", "tags")


def search(
    session: Session,
    *,
    query: str,
    search_type: str,
    category: str | None,
    tag: str | None,
    author: str | None,
    publication: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    sort: str,
    page: int,
    page_size: int,
) -> SearchResponse:
    """Search public content. An empty query returns the latest public articles."""

    text = query.strip()
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ServiceError("date_from must be on or before date_to.", 422)
    repository = SearchRepository(session)
    if not text:
        articles = _articles(
            session,
            repository,
            query="",
            page=page,
            page_size=page_size,
            sort="newest",
            category=category,
            tag=tag,
            author=author,
            publication=publication,
            date_from=date_from,
            date_to=date_to,
        )
        return _response(text, page, page_size, articles=articles)
    if _WORDS.search(text) is None:
        return _response(text, page, page_size)
    wanted = set(_SECTIONS) if search_type == "all" else {search_type}
    articles = (
        _articles(
            session,
            repository,
            query=text,
            page=page,
            page_size=page_size,
            sort=sort,
            category=category,
            tag=tag,
            author=author,
            publication=publication,
            date_from=date_from,
            date_to=date_to,
        )
        if "articles" in wanted
        else _empty_articles(page, page_size)
    )
    authors = (
        _authors(repository, query=text, page=page, page_size=page_size, category=category)
        if "authors" in wanted
        else _empty_authors(page, page_size)
    )
    publications = (
        _publications(repository, query=text, page=page, page_size=page_size)
        if "publications" in wanted
        else _empty_publications(page, page_size)
    )
    categories = (
        _taxonomy(repository.page_categories, query=text, page=page, page_size=page_size)
        if "categories" in wanted
        else _empty_taxonomy(page, page_size)
    )
    tags = (
        _taxonomy(repository.page_tags, query=text, page=page, page_size=page_size)
        if "tags" in wanted
        else _empty_taxonomy(page, page_size)
    )
    response = SearchResponse(
        query=text,
        articles=articles,
        authors=authors,
        publications=publications,
        categories=categories,
        tags=tags,
    )
    repository.record_search(
        query=text,
        search_type=search_type,
        result_count=articles.total + authors.total + publications.total + categories.total + tags.total,
        retention_days=_RETENTION_DAYS,
    )
    return response


def discover_articles(
    session: Session, *, feed: str, page: int, page_size: int
) -> ArticleCardPage:
    """Return one public article feed. Drafts and private publications are excluded."""

    repository = SearchRepository(session)
    posts, total = repository.page_articles(
        query="",
        page=page,
        page_size=page_size,
        sort="newest",
        category=None,
        tag=None,
        author=None,
        publication=None,
        date_from=None,
        date_to=None,
        featured_only=feed == "featured",
        feed=feed,
    )
    return _article_page(repository, posts, page, page_size, total)


def discover_authors(
    session: Session, *, query: str, category: str | None, page: int, page_size: int
) -> AuthorCardPage:
    """Return public authors who have at least one listed article."""

    return _authors(
        SearchRepository(session),
        query=query.strip(),
        page=page,
        page_size=page_size,
        category=category,
    )


def discover_publications(
    session: Session, *, query: str, page: int, page_size: int
) -> PublicationCardPage:
    """Return active public publications that have a listed article."""

    return _publications(
        SearchRepository(session), query=query.strip(), page=page, page_size=page_size
    )


def related_articles(session: Session, post_id: uuid.UUID, *, limit: int) -> ArticleCardPage:
    """Return similar public articles. The source article is excluded."""

    source = session.scalar(
        select(Post)
        .options(
            joinedload(Post.category),
            joinedload(Post.author),
            selectinload(Post.tags),
        )
        .where(Post.id == post_id)
    )
    if not is_publicly_listed(session, source):
        raise NotFoundError()
    assert source is not None
    repository = SearchRepository(session)
    candidates = repository.related_candidates(source, limit=_RELATED_CANDIDATES)
    source_tags = {tag.id for tag in source.tags}
    source_words = set(_TITLE_WORD.findall(plain(source.title).casefold()))
    ranked: list[tuple[int, Post]] = []
    for candidate in candidates:
        score = 0
        if source.category_id is not None and candidate.category_id == source.category_id:
            score += 5
        score += 2 * sum(1 for tag in candidate.tags if tag.id in source_tags)
        if source.publication_id is not None and candidate.publication_id == source.publication_id:
            score += 2
        if candidate.author_id == source.author_id:
            score += 1
        words = set(_TITLE_WORD.findall(plain(candidate.title).casefold()))
        score += len(source_words & words)
        if score > 0:
            ranked.append((score, candidate))
    ranked.sort(key=lambda item: (-item[0], _newest(item[1]), str(item[1].id)))
    chosen = [post for _score, post in ranked[:limit]]
    return _article_page(repository, chosen, 1, limit, len(ranked))


def suggestions(
    session: Session,
    settings: Settings,
    request,
    *,
    query: str,
    limit: int,
) -> SuggestionList:
    """Return public name suggestions. Short queries are rejected."""

    text = query.strip()
    if len(text) < 2:
        raise ServiceError("Enter at least 2 characters.", 422)
    limit_suggestions(settings, request)
    rows = SearchRepository(session).suggestions(text, limit=limit)
    return SuggestionList(
        query=text,
        items=[
            Suggestion(type=kind, id=item_id, label=label, slug=slug)  # type: ignore[arg-type]
            for kind, item_id, label, slug in rows
        ],
    )


def search_stats(session: Session) -> SearchStats:
    """Return aggregate search counts. Individual visitors are not identified."""

    since = datetime.now(UTC) - timedelta(days=_STATS_DAYS)
    total, by_type, top = SearchRepository(session).stats_since(since)
    return SearchStats(
        since=since,
        total=total,
        by_type=[TypeCount(search_type=kind, count=count) for kind, count in by_type],
        top_queries=[QueryCount(query=text, count=count) for text, count in top],
    )


def record_view(
    session: Session,
    settings: Settings,
    *,
    slug: str,
    viewer: User | None,
    visitor_id: str | None,
    source: str | None,
    user_agent: str | None,
) -> None:
    """Count one public read. Owners, repeats, and unpublished articles are not counted."""

    from app.models.article_view import ArticleView

    if visitor_id is not None and visitor_id.strip() and _VISITOR.fullmatch(visitor_id.strip()) is None:
        raise ServiceError("Visitor id must be 8 to 80 letters, numbers, underscores, or hyphens.", 422)
    if source is not None and _SOURCE.fullmatch(source) is None:
        raise ServiceError("Source must be 1 to 40 lowercase letters, numbers, underscores, or hyphens.", 422)
    found = get_published_by_slug(session, slug)
    post = found if isinstance(found, Post) else _published_post(session, found)
    if user_agent and any(marker in user_agent.casefold() for marker in _HEALTH_AGENTS):
        return
    if viewer is not None and viewer.id == post.author_id:
        return
    identity = _visitor_identity(viewer, visitor_id)
    if identity is None:
        return
    digest = hashlib.sha256(f"{settings.jwt_secret_key}:{identity}".encode()).hexdigest()
    cutoff = datetime.now(UTC) - timedelta(hours=settings.view_dedup_hours)
    existing = session.scalar(
        select(ArticleView.id).where(
            ArticleView.post_id == post.id,
            ArticleView.visitor_hash == digest,
            ArticleView.viewed_at >= cutoff,
        )
    )
    if existing is not None:
        return
    session.add(
        ArticleView(post_id=post.id, visitor_hash=digest, source=source, viewed_at=datetime.now(UTC))
    )
    session.flush()


def _published_post(session: Session, slug: str) -> Post:
    found = get_published_by_slug(session, slug)
    if not isinstance(found, Post):
        raise NotFoundError()
    return found


def _visitor_identity(viewer: User | None, visitor_id: str | None) -> str | None:
    if viewer is not None:
        return f"user:{viewer.id}"
    if visitor_id is None or not visitor_id.strip():
        return None
    return visitor_id.strip()


def _articles(session: Session, repository: SearchRepository, **filters) -> ArticleCardPage:
    page = filters["page"]
    page_size = filters["page_size"]
    posts, total = repository.page_articles(
        query=filters["query"],
        page=page,
        page_size=page_size,
        sort=filters["sort"],
        category=filters["category"],
        tag=filters["tag"],
        author=filters["author"],
        publication=filters["publication"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
    )
    return _article_page(repository, posts, page, page_size, total)


def _article_page(
    repository: SearchRepository, posts: list[Post], page: int, page_size: int, total: int
) -> ArticleCardPage:
    views, comments = repository.counts_for([post.id for post in posts])
    return ArticleCardPage(
        items=[_article_card(post, views.get(post.id, 0), comments.get(post.id, 0)) for post in posts],
        page=page,
        page_size=page_size,
        total=total,
    )


def _article_card(post: Post, view_count: int, comment_count: int) -> ArticleCard:
    return ArticleCard(
        id=post.id,
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        featured_image=post.featured_image,
        published_at=post.published_at,
        reading_time=post.reading_time,
        comment_count=comment_count,
        view_count=view_count,
        author=AuthorPublic.model_validate(post.author),
        publication=None
        if post.publication is None
        else PublicationBrief.model_validate(post.publication),
        category=None if post.category is None else CategoryBrief.model_validate(post.category),
        tags=[TagBrief.model_validate(tag) for tag in post.tags],
    )


def _authors(
    repository: SearchRepository, *, query: str, page: int, page_size: int, category: str | None
) -> AuthorCardPage:
    rows, total = repository.page_authors(
        query=query, page=page, page_size=page_size, category=category
    )
    topics = repository.author_categories([user.id for user, _count in rows])
    return AuthorCardPage(
        items=[
            AuthorCard(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                bio=user.bio,
                article_count=count,
                categories=topics.get(user.id, []),
            )
            for user, count in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def _publications(
    repository: SearchRepository, *, query: str, page: int, page_size: int
) -> PublicationCardPage:
    rows, total = repository.page_publications(query=query, page=page, page_size=page_size)
    topics = repository.publication_topics([publication.id for publication, _count in rows])
    return PublicationCardPage(
        items=[
            PublicationCard(
                id=publication.id,
                name=publication.name,
                slug=publication.slug,
                description=publication.description,
                created_at=publication.created_at,
                article_count=count,
                categories=topics.get(publication.id, ([], []))[0],
                tags=topics.get(publication.id, ([], []))[1],
            )
            for publication, count in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def _taxonomy(loader, *, query: str, page: int, page_size: int) -> TaxonomyCardPage:
    rows, total = loader(query=query, page=page, page_size=page_size)
    return TaxonomyCardPage(
        items=[
            TaxonomyCard(id=item.id, name=item.name, slug=item.slug, article_count=count)
            for item, count in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def _response(
    query: str, page: int, page_size: int, *, articles: ArticleCardPage | None = None
) -> SearchResponse:
    return SearchResponse(
        query=query,
        articles=articles or _empty_articles(page, page_size),
        authors=_empty_authors(page, page_size),
        publications=_empty_publications(page, page_size),
        categories=_empty_taxonomy(page, page_size),
        tags=_empty_taxonomy(page, page_size),
    )


def _empty_articles(page: int, page_size: int) -> ArticleCardPage:
    return ArticleCardPage(items=[], page=page, page_size=page_size, total=0)


def _empty_authors(page: int, page_size: int) -> AuthorCardPage:
    return AuthorCardPage(items=[], page=page, page_size=page_size, total=0)


def _empty_publications(page: int, page_size: int) -> PublicationCardPage:
    return PublicationCardPage(items=[], page=page, page_size=page_size, total=0)


def _empty_taxonomy(page: int, page_size: int) -> TaxonomyCardPage:
    return TaxonomyCardPage(items=[], page=page, page_size=page_size, total=0)


def _newest(post: Post) -> float:
    published = post.published_at or datetime.min.replace(tzinfo=UTC)
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return -published.timestamp()
