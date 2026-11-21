"""Add categories, tags, and article taxonomy links."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8c3b1d54a27"
down_revision: str | None = "b7e2c9a41f06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add taxonomy tables and link them to existing articles."""

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
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
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name="fk_categories_parent_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
    )
    op.create_index("ix_categories_name_key", "categories", ["name_key"], unique=True)
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
    )
    op.create_index("ix_tags_name_key", "tags", ["name_key"], unique=True)
    op.create_index("ix_tags_slug", "tags", ["slug"], unique=True)

    op.add_column("posts", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_posts_category_id_categories",
        "posts",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_posts_category_id", "posts", ["category_id"])

    op.create_table(
        "post_tags",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_post_tags_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_post_tags_tag_id_tags",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("post_id", "tag_id", name="pk_post_tags"),
    )
    op.create_index("ix_post_tags_tag_id", "post_tags", ["tag_id"])


def downgrade() -> None:
    """Remove taxonomy links and tables. Articles and accounts stay in place."""

    op.drop_index("ix_post_tags_tag_id", table_name="post_tags")
    op.drop_table("post_tags")
    op.drop_index("ix_posts_category_id", table_name="posts")
    op.drop_constraint("fk_posts_category_id_categories", "posts", type_="foreignkey")
    op.drop_column("posts", "category_id")
    op.drop_index("ix_tags_slug", table_name="tags")
    op.drop_index("ix_tags_name_key", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_index("ix_categories_name_key", table_name="categories")
    op.drop_table("categories")
