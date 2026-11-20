"""Create article and revision tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e2c9a41f06"
down_revision: str | None = "c4a8e1b27d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create posts, former slugs, and article revisions."""

    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("excerpt", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("featured_image", sa.String(length=500), nullable=True),
        sa.Column(
            "status", sa.String(length=32), server_default="draft", nullable=False
        ),
        sa.Column(
            "is_featured", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "allow_comments", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("meta_title", sa.String(length=70), nullable=True),
        sa.Column("meta_description", sa.String(length=160), nullable=True),
        sa.Column("reading_time", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name="status"
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_posts_author_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_posts"),
    )
    op.create_index("ix_posts_slug", "posts", ["slug"], unique=True)
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_published_at", "posts", ["published_at"])
    op.create_index("ix_posts_deleted_at", "posts", ["deleted_at"])
    op.create_index("ix_posts_status_published_at", "posts", ["status", "published_at"])

    op.create_table(
        "post_redirects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_post_redirects_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_post_redirects"),
    )
    op.create_index("ix_post_redirects_slug", "post_redirects", ["slug"], unique=True)
    op.create_index("ix_post_redirects_post_id", "post_redirects", ["post_id"])

    op.create_table(
        "post_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("edited_by", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("excerpt", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_post_revisions_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["edited_by"],
            ["users.id"],
            name="fk_post_revisions_edited_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_post_revisions"),
        sa.UniqueConstraint(
            "post_id", "revision_number", name="uq_post_revisions_post_id"
        ),
    )
    op.create_index("ix_post_revisions_post_id", "post_revisions", ["post_id"])
    op.create_index("ix_post_revisions_edited_by", "post_revisions", ["edited_by"])


def downgrade() -> None:
    """Remove article tables without touching authentication data."""

    op.drop_index("ix_post_revisions_edited_by", table_name="post_revisions")
    op.drop_index("ix_post_revisions_post_id", table_name="post_revisions")
    op.drop_table("post_revisions")
    op.drop_index("ix_post_redirects_post_id", table_name="post_redirects")
    op.drop_index("ix_post_redirects_slug", table_name="post_redirects")
    op.drop_table("post_redirects")
    op.drop_index("ix_posts_status_published_at", table_name="posts")
    op.drop_index("ix_posts_deleted_at", table_name="posts")
    op.drop_index("ix_posts_published_at", table_name="posts")
    op.drop_index("ix_posts_status", table_name="posts")
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_index("ix_posts_slug", table_name="posts")
    op.drop_table("posts")
