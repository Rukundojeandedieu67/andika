"""SQL aggregations over articles, counted views, and approved comments.

Timestamps are stored in UTC. Day, week, and month buckets are also UTC.
Weeks start on Monday. A bucket label can fall before ``date_from`` when the
window starts mid-week or mid-month, but the bucket only counts events inside
the requested window.

A ``date_to`` at UTC midnight includes that whole calendar day. Any other
``date_to`` is an inclusive instant. Omitted dates use the 30 days ending now.
The window cannot be longer than 366 days.

Reports are live queries. Nothing here is cached or stored in a summary table.
Views are rows already stored by the article view endpoint. Owner self-views,
repeats inside the deduplication window, health-check clients, and articles
that were not publicly listed were never inserted, so they stay at zero.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.database.types import ensure_utc
from app.models.article_view import ArticleView
from app.models.comment import Comment, CommentStatus
from app.models.post import Post, PostStatus
from app.models.publication import (
    MembershipRole,
    Publication,
    PublicationStatus,
    PublicationVisibility,
)
from app.models.user import User
from app.schemas.analytics import (
    ENGAGEMENT_FORMULA,
    AdminContent,
    AdminOverview,
    AdminPeriodComparison,
    AdminSeriesPoint,
    AdminTimeSeries,
    ArticlePerformance,
    ArticlePerformancePage,
    AuthorContribution,
    AuthorContributionPage,
    AuthorOverview,
    ContentSlice,
    PeriodComparison,
    PublicArticleRank,
    PublicationArticlePage,
    PublicationBrief,
    PublicationOverview,
    ReportWindowRead,
    SeriesPoint,
    TimeSeries,
)
from app.services.exceptions import ServiceError
from app.services.publication_access import require_active_member, require_publication

MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 30
EXPORT_ROW_LIMIT = 5000
TOP_PUBLIC_ARTICLES = 10
PeriodName = Literal["day", "week", "month"]
SortName = Literal["views", "comments", "published_at"]
ScopeName = Literal["publication", "own"]

_VIEW_LIMIT = "Views are recorded article-view events, not unique readers."
_RETURNING_LIMIT = (
    "Returning readership is not reported. Visitor hashes are not exposed, "
    "and bot filtering beyond the existing view rules is incomplete."
)
_COMMENT_LIMIT = "Only approved comments that have not been deleted are counted."
_ARTICLE_LIMIT = (
    "Draft, archived, and deleted articles are excluded. "
    "An article that is no longer published leaves these figures."
)
_SOURCE_LIMIT = "Search appearances and notification deliveries are not counted as views."
_RECORDER_LIMIT = (
    "The view recorder skips owner self-views, repeats inside the deduplication window, "
    "health-check or kube-probe clients, and articles that are not publicly listed. "
    "Those reads are not stored, so their counts stay at zero."
)
_COMMON_LIMITS = [
    _VIEW_LIMIT,
    _RETURNING_LIMIT,
    _COMMENT_LIMIT,
    _ARTICLE_LIMIT,
    _SOURCE_LIMIT,
    _RECORDER_LIMIT,
]
_CALENDAR_LIMIT = (
    "Buckets use UTC. Weeks start on Monday and months start on the first day. "
    "A bucket can be labeled before date_from, and it counts only events inside the window."
)
_ACTIVE_USER = (
    "An active user is an active account whose last sign-in falls inside the selected window. "
    "This is not a count of readers."
)
Filters = Sequence[ColumnElement[bool]]


@dataclass(frozen=True)
class ReportWindow:
    """Inclusive UTC bounds for one report."""

    start: datetime
    end: datetime
    period: PeriodName
    compare: bool

    def previous(self) -> tuple[datetime, datetime]:
        span = self.end - self.start
        previous_end = self.start - timedelta(microseconds=1)
        previous_start = self.start - span
        if previous_start > previous_end:
            return previous_end, previous_end
        return previous_start, previous_end

    def read(self) -> ReportWindowRead:
        return ReportWindowRead(date_from=self.start, date_to=self.end)


def csv_cell(value: object) -> str:
    """Keep a spreadsheet from treating text as a formula."""

    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def engagement_rate(comments: int, views: int) -> float:
    """Comments per 100 views. Zero views produce zero, not an error."""

    if views <= 0:
        return 0.0
    return round((comments / views) * 100, 2)


def average_views(views: int, articles: int) -> float:
    if articles <= 0:
        return 0.0
    return round(views / articles, 2)


def parse_window(
    date_from: datetime | None,
    date_to: datetime | None,
    period: str,
    compare: bool,
) -> ReportWindow:
    """Resolve defaults, UTC bounds, and the 366-day ceiling."""

    if period not in {"day", "week", "month"}:
        raise ServiceError("period must be day, week, or month.", 422)
    resolved: PeriodName = period  # type: ignore[assignment]
    now = datetime.now(UTC)
    end = _end_bound(date_to) if date_to is not None else now
    if date_from is not None:
        start = ensure_utc(date_from)
    elif date_to is not None:
        start = end - timedelta(days=DEFAULT_RANGE_DAYS)
    else:
        start = now - timedelta(days=DEFAULT_RANGE_DAYS)
    if start > end:
        raise ServiceError("date_from must be before or equal to date_to.", 422)
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise ServiceError("The reporting window cannot exceed 366 days.", 422)
    return ReportWindow(start=start, end=end, period=resolved, compare=compare)


def author_overview(session: Session, user: User, window: ReportWindow) -> AuthorOverview:
    filters = _author_filters(user.id)
    published = _count_posts(session, filters)
    views = _count_views(session, filters)
    comments = _count_comments(session, filters)
    return AuthorOverview(
        published_articles=published,
        publication_articles=_count_posts(
            session, [*filters, Post.publication_id.is_not(None)]
        ),
        total_views=views,
        total_approved_comments=comments,
        period_views=_count_views(session, filters, window.start, window.end),
        period_approved_comments=_count_comments(session, filters, window.start, window.end),
        average_views_per_article=average_views(views, published),
        window=window.read(),
        comparison=_comparison(session, filters, window),
        limitations=[
            *_COMMON_LIMITS,
            (
                "Figures include only articles written by the authenticated author, "
                "including articles in a publication."
            ),
            ENGAGEMENT_FORMULA,
        ],
    )


def author_articles(
    session: Session,
    user: User,
    window: ReportWindow,
    *,
    page: int,
    page_size: int,
    sort: SortName,
) -> ArticlePerformancePage:
    filters = _author_filters(user.id)
    items, total = _article_page(session, filters, window, page, page_size, sort)
    return ArticlePerformancePage(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        sort=sort,
        window=window.read(),
    )


def author_timeseries(session: Session, user: User, window: ReportWindow) -> TimeSeries:
    return _series(session, _author_filters(user.id), window, _author_series_limits())


def author_export_rows(
    session: Session, user: User, window: ReportWindow, sort: SortName
) -> tuple[list[list[object]], bool]:
    rows, truncated = _export_articles(session, _author_filters(user.id), window, sort)
    header = [
        "article_id",
        "title",
        "slug",
        "publication_name",
        "publication_slug",
        "published_at",
        "views",
        "approved_comments",
        "engagement_rate",
    ]
    body = [_article_csv(item, username, full_name, include_author=False) for item, username, full_name in rows]
    return [header, *body], truncated


def publication_overview(
    session: Session, publication_id: uuid.UUID, user: User, window: ReportWindow
) -> PublicationOverview:
    _publication, filters, scope = _publication_scope(session, publication_id, user)
    published = _count_posts(session, filters)
    views = _count_views(session, filters)
    comments = _count_comments(session, filters)
    return PublicationOverview(
        publication_id=publication_id,
        scope=scope,
        published_articles=published,
        total_views=views,
        total_approved_comments=comments,
        active_authors=_count_authors(session, filters),
        period_views=_count_views(session, filters, window.start, window.end),
        period_approved_comments=_count_comments(session, filters, window.start, window.end),
        period_articles_published=_count_posts(
            session, [*filters, *_published_between(window.start, window.end)]
        ),
        average_views_per_article=average_views(views, published),
        window=window.read(),
        comparison=_comparison(session, filters, window),
        limitations=_publication_limits(scope),
    )


def publication_articles(
    session: Session,
    publication_id: uuid.UUID,
    user: User,
    window: ReportWindow,
    *,
    page: int,
    page_size: int,
    sort: SortName,
) -> PublicationArticlePage:
    _publication, filters, scope = _publication_scope(session, publication_id, user)
    items, total = _article_page(session, filters, window, page, page_size, sort)
    return PublicationArticlePage(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        sort=sort,
        window=window.read(),
        scope=scope,
    )


def publication_authors(
    session: Session,
    publication_id: uuid.UUID,
    user: User,
    window: ReportWindow,
    *,
    page: int,
    page_size: int,
) -> AuthorContributionPage:
    _publication, filters, scope = _publication_scope(session, publication_id, user)
    articles = (
        select(
            Post.author_id.label("author_id"),
            func.count(Post.id).label("articles"),
            func.min(Post.published_at).label("first_published_at"),
            func.max(Post.published_at).label("last_published_at"),
        )
        .where(*filters)
        .group_by(Post.author_id)
        .subquery()
    )
    views = (
        select(
            Post.author_id.label("author_id"),
            func.count(ArticleView.id).label("views"),
        )
        .join(ArticleView, ArticleView.post_id == Post.id)
        .where(
            *filters,
            ArticleView.viewed_at >= window.start,
            ArticleView.viewed_at <= window.end,
        )
        .group_by(Post.author_id)
        .subquery()
    )
    comments = (
        select(
            Post.author_id.label("author_id"),
            func.count(Comment.id).label("comments"),
        )
        .join(Comment, Comment.post_id == Post.id)
        .where(
            *filters,
            Comment.deleted_at.is_(None),
            Comment.status == CommentStatus.APPROVED,
            Comment.created_at >= window.start,
            Comment.created_at <= window.end,
        )
        .group_by(Post.author_id)
        .subquery()
    )
    total = session.scalar(select(func.count()).select_from(articles)) or 0
    rows = session.execute(
        select(
            User.id,
            User.username,
            User.full_name,
            articles.c.articles,
            func.coalesce(views.c.views, 0),
            func.coalesce(comments.c.comments, 0),
            articles.c.first_published_at,
            articles.c.last_published_at,
        )
        .join(User, User.id == articles.c.author_id)
        .outerjoin(views, views.c.author_id == articles.c.author_id)
        .outerjoin(comments, comments.c.author_id == articles.c.author_id)
        .order_by(articles.c.articles.desc(), User.username.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AuthorContributionPage(
        items=[
            AuthorContribution(
                user_id=row[0],
                username=row[1],
                full_name=row[2],
                published_articles=int(row[3]),
                views=int(row[4]),
                approved_comments=int(row[5]),
                first_published_at=row[6],
                last_published_at=row[7],
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=int(total),
        scope=scope,
        window=window.read(),
    )


def publication_export_rows(
    session: Session,
    publication_id: uuid.UUID,
    user: User,
    window: ReportWindow,
    sort: SortName,
) -> tuple[list[list[object]], bool]:
    _publication, filters, _scope = _publication_scope(session, publication_id, user)
    rows, truncated = _export_articles(session, filters, window, sort)
    header = [
        "article_id",
        "title",
        "slug",
        "author_username",
        "author_name",
        "published_at",
        "views",
        "approved_comments",
        "engagement_rate",
    ]
    body = [
        _article_csv(item, username, full_name, include_author=True)
        for item, username, full_name in rows
    ]
    return [header, *body], truncated


def admin_overview(session: Session, window: ReportWindow) -> AdminOverview:
    published = _published_filters()
    return AdminOverview(
        registered_users=_count_users(session),
        active_users=_count_active_users(session, window.start, window.end),
        active_user_definition=_ACTIVE_USER,
        publications=_count_publications(session),
        active_public_publications=_count_publications(session, public=True),
        published_articles=_count_posts(session, published),
        total_views=_count_views(session, published),
        total_approved_comments=_count_comments(session, published),
        period_registrations=_count_users(session, window.start, window.end),
        period_articles_published=_count_posts(
            session, [*published, *_published_between(window.start, window.end)]
        ),
        period_publications=_count_publications(session, window.start, window.end),
        window=window.read(),
        comparison=_admin_comparison(session, window),
        limitations=[
            *_COMMON_LIMITS,
            _ACTIVE_USER,
            "Emails, visitor hashes, raw search text, and notification histories are omitted.",
            "Private, suspended, and archived publication articles are included in these counts.",
        ],
    )


def admin_timeseries(session: Session, window: ReportWindow) -> AdminTimeSeries:
    filters = _published_filters()
    base = _series(session, filters, window, [_CALENDAR_LIMIT])
    registrations = _roll(
        _daily(
            session,
            User.created_at,
            User.created_at >= window.start,
            User.created_at <= window.end,
            source=User,
        ),
        window.period,
    )
    publications = _roll(
        _daily(
            session,
            Publication.created_at,
            Publication.deleted_at.is_(None),
            Publication.created_at >= window.start,
            Publication.created_at <= window.end,
            source=Publication,
        ),
        window.period,
    )
    points = [
        AdminSeriesPoint(
            bucket_start=point.bucket_start,
            views=point.views,
            approved_comments=point.approved_comments,
            articles_published=point.articles_published,
            registrations=registrations.get(point.bucket_start, 0),
            publications_created=publications.get(point.bucket_start, 0),
        )
        for point in base.points
    ]
    return AdminTimeSeries(
        period=base.period,
        date_from=base.date_from,
        date_to=base.date_to,
        points=points,
        limitations=[*_COMMON_LIMITS, _CALENDAR_LIMIT, _ACTIVE_USER],
    )


def admin_content(session: Session, window: ReportWindow) -> AdminContent:
    published = _published_filters()
    visible = _public_publication_ids()
    return AdminContent(
        independent=_slice(session, [*published, Post.publication_id.is_(None)], window),
        public_publication=_slice(
            session, [*published, Post.publication_id.in_(visible)], window
        ),
        other_publication=_slice(
            session,
            [
                *published,
                Post.publication_id.is_not(None),
                Post.publication_id.notin_(visible),
            ],
            window,
        ),
        top_public_articles=_top_public(session, window),
        window=window.read(),
        limitations=[
            *_COMMON_LIMITS,
            (
                "other_publication counts articles in private, suspended, archived, "
                "or deleted publications. Their titles are not listed."
            ),
            (
                "top_public_articles lists at most 10 publicly listed articles with views "
                "in the window, ordered by those views."
            ),
            "Emails, visitor hashes, raw search text, and notification histories are omitted.",
        ],
    )


def admin_export_rows(
    session: Session, window: ReportWindow
) -> tuple[list[list[object]], bool]:
    content = admin_content(session, window)
    header = [
        "row_type",
        "key",
        "published_articles",
        "views",
        "approved_comments",
        "engagement_rate",
        "title",
        "slug",
    ]
    rows: list[list[object]] = [header]
    for key, item in (
        ("independent", content.independent),
        ("public_publication", content.public_publication),
        ("other_publication", content.other_publication),
    ):
        rows.append(
            [
                "summary",
                key,
                item.published_articles,
                item.views,
                item.approved_comments,
                item.engagement_rate,
                "",
                "",
            ]
        )
    for article in content.top_public_articles:
        rows.append(
            [
                "public_article",
                str(article.id),
                "",
                article.views,
                article.approved_comments,
                article.engagement_rate,
                article.title,
                article.slug,
            ]
        )
    return rows, False


def _end_bound(value: datetime) -> datetime:
    value = ensure_utc(value)
    if (
        value.hour == 0
        and value.minute == 0
        and value.second == 0
        and value.microsecond == 0
    ):
        return value + timedelta(days=1) - timedelta(microseconds=1)
    return value


def _published_filters() -> list[ColumnElement[bool]]:
    return [
        Post.deleted_at.is_(None),
        Post.status == PostStatus.PUBLISHED,
        Post.published_at.is_not(None),
    ]


def _author_filters(user_id: uuid.UUID) -> list[ColumnElement[bool]]:
    return [*_published_filters(), Post.author_id == user_id]


def _published_between(start: datetime, end: datetime) -> tuple[ColumnElement[bool], ...]:
    return (Post.published_at >= start, Post.published_at <= end)


def _public_publication_ids():
    return select(Publication.id).where(
        Publication.deleted_at.is_(None),
        Publication.status == PublicationStatus.ACTIVE,
        Publication.visibility == PublicationVisibility.PUBLIC,
    )


def _publication_scope(
    session: Session, publication_id: uuid.UUID, user: User
) -> tuple[Publication, list[ColumnElement[bool]], ScopeName]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, user)
    filters = [*_published_filters(), Post.publication_id == publication.id]
    if membership.role in {MembershipRole.OWNER, MembershipRole.EDITOR}:
        return publication, filters, "publication"
    if membership.role in {MembershipRole.AUTHOR, MembershipRole.CONTRIBUTOR}:
        return publication, [*filters, Post.author_id == user.id], "own"
    raise ServiceError("You do not have permission to view these analytics.", 403)


def _count_posts(session: Session, filters: Filters) -> int:
    return int(session.scalar(select(func.count()).select_from(Post).where(*filters)) or 0)


def _count_views(
    session: Session,
    filters: Filters,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    statement = (
        select(func.count(ArticleView.id))
        .select_from(ArticleView)
        .join(Post, Post.id == ArticleView.post_id)
        .where(*filters)
    )
    if start is not None and end is not None:
        statement = statement.where(ArticleView.viewed_at >= start, ArticleView.viewed_at <= end)
    return int(session.scalar(statement) or 0)


def _count_comments(
    session: Session,
    filters: Filters,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    statement = (
        select(func.count(Comment.id))
        .select_from(Comment)
        .join(Post, Post.id == Comment.post_id)
        .where(
            *filters,
            Comment.deleted_at.is_(None),
            Comment.status == CommentStatus.APPROVED,
        )
    )
    if start is not None and end is not None:
        statement = statement.where(Comment.created_at >= start, Comment.created_at <= end)
    return int(session.scalar(statement) or 0)


def _count_authors(session: Session, filters: Filters) -> int:
    return int(
        session.scalar(select(func.count(func.distinct(Post.author_id))).where(*filters)) or 0
    )


def _count_users(
    session: Session, start: datetime | None = None, end: datetime | None = None
) -> int:
    statement = select(func.count()).select_from(User)
    if start is not None and end is not None:
        statement = statement.where(User.created_at >= start, User.created_at <= end)
    return int(session.scalar(statement) or 0)


def _count_active_users(session: Session, start: datetime, end: datetime) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.is_active.is_(True),
                User.last_login_at.is_not(None),
                User.last_login_at >= start,
                User.last_login_at <= end,
            )
        )
        or 0
    )


def _count_publications(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    *,
    public: bool = False,
) -> int:
    statement = select(func.count()).select_from(Publication).where(Publication.deleted_at.is_(None))
    if public:
        statement = statement.where(
            Publication.status == PublicationStatus.ACTIVE,
            Publication.visibility == PublicationVisibility.PUBLIC,
        )
    if start is not None and end is not None:
        statement = statement.where(
            Publication.created_at >= start, Publication.created_at <= end
        )
    return int(session.scalar(statement) or 0)


def _comparison(
    session: Session, filters: Filters, window: ReportWindow
) -> PeriodComparison | None:
    if not window.compare:
        return None
    start, end = window.previous()
    return PeriodComparison(
        date_from=start,
        date_to=end,
        views=_count_views(session, filters, start, end),
        approved_comments=_count_comments(session, filters, start, end),
        articles_published=_count_posts(session, [*filters, *_published_between(start, end)]),
    )


def _admin_comparison(session: Session, window: ReportWindow) -> AdminPeriodComparison | None:
    current = _comparison(session, _published_filters(), window)
    if current is None:
        return None
    start, end = window.previous()
    return AdminPeriodComparison(
        date_from=current.date_from,
        date_to=current.date_to,
        views=current.views,
        approved_comments=current.approved_comments,
        articles_published=current.articles_published,
        registrations=_count_users(session, start, end),
        publications_created=_count_publications(session, start, end),
    )


def _article_page(
    session: Session,
    filters: Filters,
    window: ReportWindow,
    page: int,
    page_size: int,
    sort: SortName,
) -> tuple[list[ArticlePerformance], int]:
    total = _count_posts(session, filters)
    rows = _article_statement(filters, window, sort).offset((page - 1) * page_size).limit(page_size)
    return [_performance(row) for row in session.execute(rows).all()], total


def _export_articles(
    session: Session, filters: Filters, window: ReportWindow, sort: SortName
) -> tuple[list[tuple[ArticlePerformance, str, str | None]], bool]:
    statement = _article_statement(filters, window, sort).limit(EXPORT_ROW_LIMIT + 1)
    loaded = [_loaded(row) for row in session.execute(statement).all()]
    truncated = len(loaded) > EXPORT_ROW_LIMIT
    return loaded[:EXPORT_ROW_LIMIT], truncated


def _article_statement(filters: Filters, window: ReportWindow, sort: SortName):
    views = (
        select(
            ArticleView.post_id.label("post_id"),
            func.count(ArticleView.id).label("total"),
        )
        .where(
            ArticleView.post_id.in_(select(Post.id).where(*filters)),
            ArticleView.viewed_at >= window.start,
            ArticleView.viewed_at <= window.end,
        )
        .group_by(ArticleView.post_id)
        .subquery()
    )
    comments = (
        select(Comment.post_id.label("post_id"), func.count(Comment.id).label("total"))
        .where(
            Comment.post_id.in_(select(Post.id).where(*filters)),
            Comment.deleted_at.is_(None),
            Comment.status == CommentStatus.APPROVED,
            Comment.created_at >= window.start,
            Comment.created_at <= window.end,
        )
        .group_by(Comment.post_id)
        .subquery()
    )
    view_count = func.coalesce(views.c.total, 0)
    comment_count = func.coalesce(comments.c.total, 0)
    statement = (
        select(
            Post,
            view_count,
            comment_count,
            Publication.name,
            Publication.slug,
            User.username,
            User.full_name,
        )
        .join(User, User.id == Post.author_id)
        .outerjoin(views, views.c.post_id == Post.id)
        .outerjoin(comments, comments.c.post_id == Post.id)
        .outerjoin(Publication, Publication.id == Post.publication_id)
        .where(*filters)
    )
    if sort == "views":
        ordering = (view_count.desc(), Post.published_at.desc(), Post.id.desc())
    elif sort == "comments":
        ordering = (comment_count.desc(), Post.published_at.desc(), Post.id.desc())
    else:
        ordering = (Post.published_at.desc(), Post.id.desc())
    return statement.order_by(*ordering)


def _loaded(row: object) -> tuple[ArticlePerformance, str, str | None]:
    username = row[5]  # type: ignore[index]
    full_name = row[6]  # type: ignore[index]
    return _performance(row), str(username), full_name


def _performance(row: object) -> ArticlePerformance:
    post, views, comments, publication_name, publication_slug = row[:5]  # type: ignore[index]
    publication = None
    if post.publication_id is not None and publication_name is not None:
        publication = PublicationBrief(
            id=post.publication_id,
            name=publication_name,
            slug=publication_slug,
        )
    view_count = int(views or 0)
    comment_count = int(comments or 0)
    return ArticlePerformance(
        id=post.id,
        title=post.title,
        slug=post.slug,
        published_at=post.published_at,
        publication=publication,
        views=view_count,
        approved_comments=comment_count,
        engagement_rate=engagement_rate(comment_count, view_count),
    )


def _article_csv(
    item: ArticlePerformance,
    username: str,
    full_name: str | None,
    *,
    include_author: bool,
) -> list[object]:
    published = item.published_at.isoformat() if item.published_at is not None else ""
    if include_author:
        return [
            str(item.id),
            item.title,
            item.slug,
            username,
            full_name or "",
            published,
            item.views,
            item.approved_comments,
            item.engagement_rate,
        ]
    publication_name = item.publication.name if item.publication is not None else ""
    publication_slug = item.publication.slug if item.publication is not None else ""
    return [
        str(item.id),
        item.title,
        item.slug,
        publication_name,
        publication_slug,
        published,
        item.views,
        item.approved_comments,
        item.engagement_rate,
    ]


def _series(
    session: Session, filters: Filters, window: ReportWindow, limitations: list[str]
) -> TimeSeries:
    views = _roll(
        _daily(
            session,
            ArticleView.viewed_at,
            *filters,
            ArticleView.viewed_at >= window.start,
            ArticleView.viewed_at <= window.end,
            joined=True,
        ),
        window.period,
    )
    comments = _roll(
        _daily(
            session,
            Comment.created_at,
            *filters,
            Comment.deleted_at.is_(None),
            Comment.status == CommentStatus.APPROVED,
            Comment.created_at >= window.start,
            Comment.created_at <= window.end,
            joined=True,
            comments=True,
        ),
        window.period,
    )
    articles = _roll(
        _daily(
            session,
            Post.published_at,
            *filters,
            *_published_between(window.start, window.end),
            source=Post,
        ),
        window.period,
    )
    points = [
        SeriesPoint(
            bucket_start=bucket,
            views=views.get(bucket, 0),
            approved_comments=comments.get(bucket, 0),
            articles_published=articles.get(bucket, 0),
        )
        for bucket in _bucket_starts(window.start, window.end, window.period)
    ]
    return TimeSeries(
        period=window.period,
        date_from=window.start,
        date_to=window.end,
        points=points,
        limitations=limitations,
    )


def _daily(
    session: Session,
    column,
    *predicates: ColumnElement[bool],
    joined: bool = False,
    comments: bool = False,
    source: object | None = None,
) -> dict[date, int]:
    dialect = session.get_bind().dialect.name
    day = _utc_day(column, dialect)
    if comments:
        statement = (
            select(day, func.count(Comment.id))
            .select_from(Comment)
            .join(Post, Post.id == Comment.post_id)
            .where(*predicates)
            .group_by(day)
        )
    elif joined:
        statement = (
            select(day, func.count(ArticleView.id))
            .select_from(ArticleView)
            .join(Post, Post.id == ArticleView.post_id)
            .where(*predicates)
            .group_by(day)
        )
    else:
        statement = select(day, func.count())
        if source is not None:
            statement = statement.select_from(source)
        statement = statement.where(*predicates).group_by(day)
    found: dict[date, int] = {}
    for raw, count in session.execute(statement).all():
        if raw is None:
            continue
        found[_as_date(raw)] = int(count)
    return found


def _utc_day(column, dialect_name: str):
    if dialect_name == "postgresql":
        return cast(func.timezone("UTC", column), Date)
    return func.date(column)


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _roll(daily: dict[date, int], period: PeriodName) -> dict[date, int]:
    rolled: dict[date, int] = {}
    for day, count in daily.items():
        key = _align(day, period)
        rolled[key] = rolled.get(key, 0) + count
    return rolled


def _bucket_starts(start: datetime, end: datetime, period: PeriodName) -> list[date]:
    cursor = _align(start.date(), period)
    last = _align(end.date(), period)
    points: list[date] = []
    while cursor <= last:
        points.append(cursor)
        cursor = _advance(cursor, period)
    return points


def _align(day: date, period: PeriodName) -> date:
    if period == "week":
        return day - timedelta(days=day.weekday())
    if period == "month":
        return day.replace(day=1)
    return day


def _advance(day: date, period: PeriodName) -> date:
    if period == "week":
        return day + timedelta(days=7)
    if period == "month":
        if day.month == 12:
            return date(day.year + 1, 1, 1)
        return date(day.year, day.month + 1, 1)
    return day + timedelta(days=1)


def _slice(session: Session, filters: Filters, window: ReportWindow) -> ContentSlice:
    views = _count_views(session, filters, window.start, window.end)
    comments = _count_comments(session, filters, window.start, window.end)
    return ContentSlice(
        published_articles=_count_posts(session, filters),
        views=views,
        approved_comments=comments,
        engagement_rate=engagement_rate(comments, views),
    )


def _top_public(session: Session, window: ReportWindow) -> list[PublicArticleRank]:
    visible = _public_publication_ids()
    filters = [
        *_published_filters(),
        or_(Post.publication_id.is_(None), Post.publication_id.in_(visible)),
    ]
    items, _total = _article_page(session, filters, window, 1, TOP_PUBLIC_ARTICLES, "views")
    return [
        PublicArticleRank(
            id=item.id,
            title=item.title,
            slug=item.slug,
            views=item.views,
            approved_comments=item.approved_comments,
            engagement_rate=item.engagement_rate,
        )
        for item in items
        if item.views > 0
    ]


def _author_series_limits() -> list[str]:
    return [
        *_COMMON_LIMITS,
        _CALENDAR_LIMIT,
        "The series includes only articles written by the authenticated author.",
    ]


def _publication_limits(scope: ScopeName) -> list[str]:
    if scope == "own":
        own = (
            "Authors and contributors see only articles they wrote in this publication. "
            "There is no publication setting that grants them other members' analytics."
        )
    else:
        own = (
            "Owners and editors see this publication's published articles. "
            "Members' independent articles are not included."
        )
    return [*_COMMON_LIMITS, own]

