"""Public search and discovery responses. Article bodies are not included."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryBrief
from app.schemas.post import AuthorPublic
from app.schemas.tag import TagBrief

SearchType = Literal["all", "articles", "authors", "publications", "categories", "tags"]
ArticleSort = Literal["relevance", "newest", "oldest", "most_viewed", "most_commented"]
ArticleFeed = Literal["latest", "trending", "popular", "discussed", "featured"]
SuggestionType = Literal["article", "author", "publication", "category", "tag"]


class PublicationBrief(BaseModel):
    """Public publication fields shown on a search card."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class ArticleCard(BaseModel):
    """Article metadata for search and discovery. The body is omitted."""

    id: UUID
    title: str
    slug: str
    excerpt: str | None
    featured_image: str | None
    published_at: datetime | None
    reading_time: int
    comment_count: int
    view_count: int
    author: AuthorPublic
    publication: PublicationBrief | None = None
    category: CategoryBrief | None = None
    tags: list[TagBrief] = Field(default_factory=list)


class ArticleCardPage(BaseModel):
    items: list[ArticleCard]
    page: int
    page_size: int
    total: int


class AuthorCard(BaseModel):
    """A public author profile plus how many public articles they have."""

    id: UUID
    username: str
    full_name: str | None
    avatar_url: str | None
    bio: str | None
    article_count: int
    categories: list[str] = Field(default_factory=list)


class AuthorCardPage(BaseModel):
    items: list[AuthorCard]
    page: int
    page_size: int
    total: int


class PublicationCard(BaseModel):
    """An active public publication and its public article count."""

    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    article_count: int
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PublicationCardPage(BaseModel):
    items: list[PublicationCard]
    page: int
    page_size: int
    total: int


class TaxonomyCard(BaseModel):
    id: UUID
    name: str
    slug: str
    article_count: int


class TaxonomyCardPage(BaseModel):
    items: list[TaxonomyCard]
    page: int
    page_size: int
    total: int


class SearchResponse(BaseModel):
    """One page of each requested result kind. Unused kinds are empty."""

    query: str
    articles: ArticleCardPage
    authors: AuthorCardPage
    publications: PublicationCardPage
    categories: TaxonomyCardPage
    tags: TaxonomyCardPage


class Suggestion(BaseModel):
    type: SuggestionType
    id: UUID
    label: str
    slug: str | None = None


class SuggestionList(BaseModel):
    query: str
    items: list[Suggestion]


class QueryCount(BaseModel):
    query: str
    count: int


class TypeCount(BaseModel):
    search_type: str
    count: int


class SearchStats(BaseModel):
    """Aggregates for administrators. Individual visitors are not identified."""

    since: datetime
    total: int
    by_type: list[TypeCount]
    top_queries: list[QueryCount]
