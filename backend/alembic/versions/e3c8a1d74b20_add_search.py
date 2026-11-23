"""Add search documents, view events, and search analytics."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3c8a1d74b20"
down_revision: str | None = "d7b4e2a91c58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRGM_INDEXES = (
    ("ix_posts_title_trgm", "posts", "title"),
    ("ix_users_username_trgm", "users", "username"),
    ("ix_users_full_name_trgm", "users", "full_name"),
    ("ix_publications_name_trgm", "publications", "name"),
    ("ix_categories_name_trgm", "categories", "name"),
    ("ix_tags_name_trgm", "tags", "name"),
)


def upgrade() -> None:
    """Add searchable text and the tables that support discovery."""

    op.add_column(
        "posts",
        sa.Column("search_document", sa.Text(), server_default="", nullable=False),
    )
    op.create_table(
        "article_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column(
            "viewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_views_post_id", "article_views", ["post_id"])
    op.create_index("ix_article_views_viewed_at", "article_views", ["viewed_at"])
    op.create_index(
        "ix_article_views_post_id_viewed_at", "article_views", ["post_id", "viewed_at"]
    )
    op.create_index(
        "ix_article_views_post_id_visitor_hash_viewed_at",
        "article_views",
        ["post_id", "visitor_hash", "viewed_at"],
    )
    op.create_table(
        "search_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False),
        sa.Column("search_type", sa.String(length=16), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_events_search_type", "search_events", ["search_type"])
    op.create_index("ix_search_events_created_at", "search_events", ["created_at"])
    op.create_index(
        "ix_search_events_created_at_search_type",
        "search_events",
        ["created_at", "search_type"],
    )
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE posts ADD COLUMN search_vector tsvector")
    op.execute(
        """
        CREATE FUNCTION posts_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple', coalesce(NEW.search_document, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER posts_search_vector_trigger
        BEFORE INSERT OR UPDATE OF search_document ON posts
        FOR EACH ROW EXECUTE FUNCTION posts_search_vector_update()
        """
    )
    op.execute(
        """
        UPDATE posts
        SET search_document = btrim(concat_ws(
            ' ', title, subtitle, excerpt, left(content, 20000)
        ))
        """
    )
    op.execute(
        "CREATE INDEX ix_posts_search_vector ON posts USING gin (search_vector)"
    )
    if _enable_trgm(bind):
        for name, table, column in _TRGM_INDEXES:
            op.execute(
                f"CREATE INDEX {name} ON {table} USING gin ({column} gin_trgm_ops)"
            )


def downgrade() -> None:
    """Remove search tables, the vector, and the indexes added above."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name, _table, _column in _TRGM_INDEXES:
            op.execute(f"DROP INDEX IF EXISTS {name}")
        op.execute("DROP INDEX IF EXISTS ix_posts_search_vector")
        op.execute("DROP TRIGGER IF EXISTS posts_search_vector_trigger ON posts")
        op.execute("DROP FUNCTION IF EXISTS posts_search_vector_update()")
        op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS search_vector")
    op.drop_index("ix_search_events_created_at_search_type", table_name="search_events")
    op.drop_index("ix_search_events_created_at", table_name="search_events")
    op.drop_index("ix_search_events_search_type", table_name="search_events")
    op.drop_table("search_events")
    op.drop_index(
        "ix_article_views_post_id_visitor_hash_viewed_at", table_name="article_views"
    )
    op.drop_index("ix_article_views_post_id_viewed_at", table_name="article_views")
    op.drop_index("ix_article_views_viewed_at", table_name="article_views")
    op.drop_index("ix_article_views_post_id", table_name="article_views")
    op.drop_table("article_views")
    op.drop_column("posts", "search_document")


def _enable_trgm(connection) -> bool:
    """Create pg_trgm when the role is allowed to. Leave search working if it is not."""

    installed = connection.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
    ).scalar()
    if installed:
        return True
    connection.execute(sa.text("SAVEPOINT andika_trgm"))
    try:
        connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    except sa.exc.SQLAlchemyError:
        connection.execute(sa.text("ROLLBACK TO SAVEPOINT andika_trgm"))
        return False
    connection.execute(sa.text("RELEASE SAVEPOINT andika_trgm"))
    return True
