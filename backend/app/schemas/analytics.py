"""Analytics responses. Counts are computed in SQL and are current at request time."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ENGAGEMENT_FORMULA = (
    "engagement_rate = (approved_comments / views) * 100, or 0 when views are 0. "
    "Views are recorded read events, not unique readers."
)


class ReportWindowRead(BaseModel):
    """The UTC window actually used after defaults and date-boundary rules."""

    date_from: datetime
    date_to: datetime
    timezone: Literal["UTC"] = "UTC"


class PeriodComparison(BaseModel):
    """The immediately previous window of the same duration."""

    date_from: datetime
    date_to: datetime
    views: int
    approved_comments: int
    articles_published: int


class AdminPeriodComparison(PeriodComparison):
    """Previous-window platform totals."""

    registrations: int
    publications_created: int


class PublicationBrief(BaseModel):
    """Public identity of a publication attached to an article the caller may see."""

    id: UUID
    name: str
    slug: str


class ArticlePerformance(BaseModel):
    """One currently published article and its windowed engagement."""

    id: UUID
    title: str
    slug: str
    published_at: datetime
    publication: PublicationBrief | None
    views: int
    approved_comments: int
    engagement_rate: float = Field(description=ENGAGEMENT_FORMULA)


class ArticlePerformancePage(BaseModel):
    """A page of article performance rows."""

    items: list[ArticlePerformance]
    page: int
    page_size: int
    total: int
    sort: Literal["views", "comments", "published_at"]
    window: ReportWindowRead
    engagement_rate_formula: str = ENGAGEMENT_FORMULA


class PublicationArticlePage(ArticlePerformancePage):
    """Article performance limited by the caller's publication role."""

    scope: Literal["publication", "own"]


class AuthorOverview(BaseModel):
    """Lifetime totals for the caller's published articles, plus one window."""

    published_articles: int
    publication_articles: int
    total_views: int
    total_approved_comments: int
    period_views: int
    period_approved_comments: int
    average_views_per_article: float = Field(
        description="total_views / published_articles, or 0 when there are no published articles."
    )
    window: ReportWindowRead
    comparison: PeriodComparison | None
    limitations: list[str]


class SeriesPoint(BaseModel):
    """One UTC day, Monday-starting week, or calendar month."""

    bucket_start: date
    views: int
    approved_comments: int
    articles_published: int


class TimeSeries(BaseModel):
    """A zero-filled series. Empty buckets stay in the response with zeros."""

    period: Literal["day", "week", "month"]
    timezone: Literal["UTC"] = "UTC"
    week_starts_on: Literal["monday"] = "monday"
    date_from: datetime
    date_to: datetime
    points: list[SeriesPoint]
    limitations: list[str]


class AuthorContribution(BaseModel):
    """One member's published work inside a single publication."""

    user_id: UUID
    username: str
    full_name: str | None
    published_articles: int
    views: int = Field(description="Views during the selected window.")
    approved_comments: int = Field(description="Approved comments during the selected window.")
    first_published_at: datetime | None
    last_published_at: datetime | None


class AuthorContributionPage(BaseModel):
    """Publication members who currently have a published article in scope."""

    items: list[AuthorContribution]
    page: int
    page_size: int
    total: int
    scope: Literal["publication", "own"]
    window: ReportWindowRead


class PublicationOverview(BaseModel):
    """Published-article totals for one publication, or for the caller's own articles there."""

    publication_id: UUID
    scope: Literal["publication", "own"]
    published_articles: int
    total_views: int
    total_approved_comments: int
    active_authors: int = Field(
        description="Distinct authors of currently published articles in this scope."
    )
    period_views: int
    period_approved_comments: int
    period_articles_published: int
    average_views_per_article: float
    window: ReportWindowRead
    comparison: PeriodComparison | None
    limitations: list[str]


class AdminOverview(BaseModel):
    """Platform totals. No addresses, visitor hashes, or message bodies."""

    registered_users: int
    active_users: int
    active_user_definition: str
    publications: int
    active_public_publications: int
    published_articles: int
    total_views: int
    total_approved_comments: int
    period_registrations: int
    period_articles_published: int
    period_publications: int
    window: ReportWindowRead
    comparison: AdminPeriodComparison | None
    limitations: list[str]


class AdminSeriesPoint(SeriesPoint):
    """Platform series, including new accounts and publications."""

    registrations: int
    publications_created: int


class AdminTimeSeries(BaseModel):
    """Zero-filled platform series."""

    period: Literal["day", "week", "month"]
    timezone: Literal["UTC"] = "UTC"
    week_starts_on: Literal["monday"] = "monday"
    date_from: datetime
    date_to: datetime
    points: list[AdminSeriesPoint]
    limitations: list[str]


class ContentSlice(BaseModel):
    """Published articles in one visibility group, with windowed events."""

    published_articles: int
    views: int
    approved_comments: int
    engagement_rate: float = Field(description=ENGAGEMENT_FORMULA)


class PublicArticleRank(BaseModel):
    """A publicly listed article. Private titles are not included."""

    id: UUID
    title: str
    slug: str
    views: int
    approved_comments: int
    engagement_rate: float = Field(description=ENGAGEMENT_FORMULA)


class AdminContent(BaseModel):
    """Content totals split so private work stays aggregated."""

    independent: ContentSlice
    public_publication: ContentSlice
    other_publication: ContentSlice
    top_public_articles: list[PublicArticleRank]
    window: ReportWindowRead
    engagement_rate_formula: str = ENGAGEMENT_FORMULA
    limitations: list[str]
