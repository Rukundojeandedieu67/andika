"""Add media records and link articles to a featured image."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4b8d2e91c36"
down_revision: str | None = "e8c3b1d54a27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add media storage and an optional featured image on existing articles."""

    op.create_table(
        "media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("storage_provider", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("file_extension", sa.String(length=8), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(length=300), nullable=True),
        sa.Column("caption", sa.String(length=500), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name="status"
        ),
        sa.CheckConstraint(
            "storage_provider IN ('local', 's3')", name="provider"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_media_owner_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_media"),
    )
    op.create_index("ix_media_owner_id", "media", ["owner_id"])
    op.create_index("ix_media_storage_key", "media", ["storage_key"], unique=True)
    op.create_index("ix_media_mime_type", "media", ["mime_type"])
    op.create_index("ix_media_checksum", "media", ["checksum"])
    op.create_index("ix_media_status", "media", ["status"])
    op.create_index("ix_media_deleted_at", "media", ["deleted_at"])
    op.create_index(
        "ix_media_owner_id_created_at", "media", ["owner_id", "created_at"]
    )
    op.create_index(
        "uq_media_owner_checksum_active",
        "media",
        ["owner_id", "checksum"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "media_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('original', 'large', 'medium', 'thumbnail')", name="kind"
        ),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
            name="fk_media_variants_media_id_media",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_media_variants"),
        sa.UniqueConstraint(
            "media_id", "kind", name="uq_media_variants_media_id_kind"
        ),
    )
    op.create_index("ix_media_variants_media_id", "media_variants", ["media_id"])
    op.create_index(
        "ix_media_variants_storage_key",
        "media_variants",
        ["storage_key"],
        unique=True,
    )

    op.add_column("posts", sa.Column("featured_image_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_posts_featured_image_id_media",
        "posts",
        "media",
        ["featured_image_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_posts_featured_image_id", "posts", ["featured_image_id"])


def downgrade() -> None:
    """Remove media links and tables. Articles and their URL images stay."""

    op.drop_index("ix_posts_featured_image_id", table_name="posts")
    op.drop_constraint(
        "fk_posts_featured_image_id_media", "posts", type_="foreignkey"
    )
    op.drop_column("posts", "featured_image_id")
    op.drop_index("ix_media_variants_storage_key", table_name="media_variants")
    op.drop_index("ix_media_variants_media_id", table_name="media_variants")
    op.drop_table("media_variants")
    op.drop_index("uq_media_owner_checksum_active", table_name="media")
    op.drop_index("ix_media_owner_id_created_at", table_name="media")
    op.drop_index("ix_media_deleted_at", table_name="media")
    op.drop_index("ix_media_status", table_name="media")
    op.drop_index("ix_media_checksum", table_name="media")
    op.drop_index("ix_media_mime_type", table_name="media")
    op.drop_index("ix_media_storage_key", table_name="media")
    op.drop_index("ix_media_owner_id", table_name="media")
    op.drop_table("media")
