"""Plain-text search documents and portable matching for the test database."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.post import Post

_TAGS = re.compile(r"<[^>]*>")
_TOKENS = re.compile(r"\w+", re.UNICODE)
_MAX_DOCUMENT = 20_000


def plain(value: str | None) -> str:
    """Collapse whitespace and drop HTML tags."""

    if not value:
        return ""
    return " ".join(_TAGS.sub(" ", value).split())


def assign_search_document(post: Post) -> None:
    """Rebuild one article's searchable text from the fields already on the row."""

    category = post.category.name if post.category is not None else ""
    tags = " ".join(tag.name for tag in post.tags)
    author_name = ""
    username = ""
    if post.author is not None:
        author_name = post.author.full_name or ""
        username = post.author.username
    publication = post.publication.name if post.publication is not None else ""
    document = plain(
        " ".join(
            (
                post.title,
                post.subtitle or "",
                post.excerpt or "",
                post.content,
                category,
                tags,
                author_name,
                username,
                publication,
            )
        )
    )
    post.search_document = document[:_MAX_DOCUMENT]


def refresh_for_author(session: Session, author_id: uuid.UUID) -> None:
    _refresh(session, Post.author_id == author_id)


def refresh_for_publication(session: Session, publication_id: uuid.UUID) -> None:
    _refresh(session, Post.publication_id == publication_id)


def refresh_for_category(session: Session, category_id: uuid.UUID) -> None:
    _refresh(session, Post.category_id == category_id)


def refresh_for_tag(session: Session, tag_id: uuid.UUID) -> None:
    from app.models.tag import Tag

    _refresh(session, Post.tags.any(Tag.id == tag_id))


def document_matches(document: str, query: str) -> bool:
    """Substring match, with a one-character typo allowance on longer words."""

    text = plain(document).casefold()
    tokens = [token.casefold() for token in _TOKENS.findall(query)]
    if not text or not tokens:
        return False
    words = text.split()
    for token in tokens:
        if token in text:
            continue
        if len(token) < 5 or not any(
            abs(len(word) - len(token)) <= 1 and _distance(token, word) <= 1
            for word in words
        ):
            return False
    return True


def portable_score(title: str, document: str, query: str) -> float:
    """Higher when the query appears in the title. Zero means no match."""

    if not document_matches(document, query):
        return 0
    score = 1.0
    folded = plain(query).casefold()
    if folded and folded in title.casefold():
        score += 3
    return score


def _refresh(session: Session, clause) -> None:
    posts = (
        session.scalars(
            select(Post)
            .options(
                joinedload(Post.author),
                joinedload(Post.category),
                joinedload(Post.publication),
                selectinload(Post.tags),
            )
            .where(clause, Post.deleted_at.is_(None))
        )
        .unique()
        .all()
    )
    for post in posts:
        assign_search_document(post)


def _distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (left_char != right_char)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]
