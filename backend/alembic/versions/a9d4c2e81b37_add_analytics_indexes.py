"""Add indexes that support analytics date ranges.

These indexes do not store totals. Every report reads the current rows.

Revision ID: a9d4c2e81b37
Revises: f8b1d4c62a90
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9d4c2e81b37"
down_revision: str | None = "f8b1d4c62a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Index the columns analytics filters by author, publication, and time."""

    op.create_index("ix_users_created_at", "users", ["created_at"])
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"])
    op.create_index("ix_publications_created_at", "publications", ["created_at"])
    op.create_index(
        "ix_posts_author_status_published_at",
        "posts",
        ["author_id", "status", "published_at"],
    )
    op.create_index(
        "ix_posts_publication_status_published_at",
        "posts",
        ["publication_id", "status", "published_at"],
    )
    op.create_index(
        "ix_comments_approved_created_at",
        "comments",
        ["status", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Remove the analytics indexes. Source rows stay in place."""

    op.drop_index("ix_comments_approved_created_at", table_name="comments")
    op.drop_index("ix_posts_publication_status_published_at", table_name="posts")
    op.drop_index("ix_posts_author_status_published_at", table_name="posts")
    op.drop_index("ix_publications_created_at", table_name="publications")
    op.drop_index("ix_users_last_login_at", table_name="users")
    op.drop_index("ix_users_created_at", table_name="users")
