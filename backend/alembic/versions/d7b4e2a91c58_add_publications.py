"""Add publications, memberships, invitations, and editorial history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7b4e2a91c58"
down_revision: str | None = "c5d1a8e24f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add publication tables and a nullable link from existing articles."""

    op.create_table(
        "publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_media_id", sa.Uuid(), nullable=True),
        sa.Column("cover_media_id", sa.Uuid(), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "requires_review", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "editors_can_invite", sa.Boolean(), server_default=sa.true(), nullable=False
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "visibility IN ('public', 'private')",
            name="visibility",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'archived')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["logo_media_id"],
            ["media.id"],
            name="fk_publications_logo_media_id_media",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cover_media_id"],
            ["media.id"],
            name="fk_publications_cover_media_id_media",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_publications_owner_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publications"),
    )
    op.create_index("ix_publications_slug", "publications", ["slug"], unique=True)
    op.create_index("ix_publications_logo_media_id", "publications", ["logo_media_id"])
    op.create_index("ix_publications_cover_media_id", "publications", ["cover_media_id"])
    op.create_index("ix_publications_owner_id", "publications", ["owner_id"])
    op.create_index("ix_publications_visibility", "publications", ["visibility"])
    op.create_index("ix_publications_status", "publications", ["status"])
    op.create_index("ix_publications_deleted_at", "publications", ["deleted_at"])

    op.create_table(
        "publication_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'author', 'contributor')",
            name="role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'suspended', 'removed')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["publications.id"],
            name="fk_publication_memberships_publication_id_publications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_publication_memberships_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publication_memberships"),
        sa.UniqueConstraint(
            "publication_id",
            "user_id",
            name="uq_publication_memberships_publication_id_user_id",
        ),
    )
    op.create_index(
        "ix_publication_memberships_publication_id",
        "publication_memberships",
        ["publication_id"],
    )
    op.create_index(
        "ix_publication_memberships_user_id",
        "publication_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_publication_memberships_status",
        "publication_memberships",
        ["status"],
    )
    op.create_index(
        "uq_publication_memberships_one_owner",
        "publication_memberships",
        ["publication_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND status = 'active'"),
    )

    op.create_table(
        "publication_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_key", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('editor', 'author', 'contributor')",
            name="role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["publications.id"],
            name="fk_publication_invitations_publication_id_publications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["users.id"],
            name="fk_publication_invitations_invited_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publication_invitations"),
    )
    op.create_index(
        "ix_publication_invitations_publication_id",
        "publication_invitations",
        ["publication_id"],
    )
    op.create_index(
        "ix_publication_invitations_email_key",
        "publication_invitations",
        ["email_key"],
    )
    op.create_index(
        "ix_publication_invitations_token_hash",
        "publication_invitations",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_publication_invitations_invited_by_id",
        "publication_invitations",
        ["invited_by_id"],
    )
    op.create_index(
        "ix_publication_invitations_status",
        "publication_invitations",
        ["status"],
    )
    op.create_index(
        "ix_publication_invitations_expires_at",
        "publication_invitations",
        ["expires_at"],
    )
    op.create_index(
        "uq_publication_invitations_pending_email",
        "publication_invitations",
        ["publication_id", "email_key"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "publication_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("previous_value", sa.String(length=500), nullable=True),
        sa.Column("new_value", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["publications.id"],
            name="fk_publication_audit_logs_publication_id_publications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_publication_audit_logs_actor_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            name="fk_publication_audit_logs_target_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publication_audit_logs"),
    )
    op.create_index(
        "ix_publication_audit_logs_publication_id",
        "publication_audit_logs",
        ["publication_id"],
    )
    op.create_index(
        "ix_publication_audit_logs_actor_id",
        "publication_audit_logs",
        ["actor_id"],
    )
    op.create_index(
        "ix_publication_audit_logs_target_user_id",
        "publication_audit_logs",
        ["target_user_id"],
    )
    op.create_index(
        "ix_publication_audit_logs_created_at",
        "publication_audit_logs",
        ["created_at"],
    )

    op.add_column("posts", sa.Column("publication_id", sa.Uuid(), nullable=True))
    op.add_column("posts", sa.Column("editorial_status", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_posts_publication_id_publications",
        "posts",
        "publications",
        ["publication_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "editorial_status",
        "posts",
        "editorial_status IS NULL OR editorial_status IN "
        "('draft', 'submitted', 'in_review', 'changes_requested', 'approved', 'published')",
    )
    op.create_index("ix_posts_publication_id", "posts", ["publication_id"])
    op.create_index("ix_posts_editorial_status", "posts", ["editorial_status"])

    op.create_table(
        "editorial_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('draft', 'submitted', 'in_review', 'changes_requested', 'approved', 'published')",
            name="from_status",
        ),
        sa.CheckConstraint(
            "to_status IN "
            "('draft', 'submitted', 'in_review', 'changes_requested', 'approved', 'published')",
            name="to_status",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_editorial_events_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_editorial_events_actor_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_editorial_events"),
    )
    op.create_index("ix_editorial_events_post_id", "editorial_events", ["post_id"])
    op.create_index("ix_editorial_events_actor_id", "editorial_events", ["actor_id"])
    op.create_index("ix_editorial_events_created_at", "editorial_events", ["created_at"])
    op.create_index(
        "ix_editorial_events_post_id_created_at",
        "editorial_events",
        ["post_id", "created_at"],
    )


def downgrade() -> None:
    """Remove publication tables and the article link. Independent articles remain."""

    op.drop_index("ix_editorial_events_post_id_created_at", table_name="editorial_events")
    op.drop_index("ix_editorial_events_created_at", table_name="editorial_events")
    op.drop_index("ix_editorial_events_actor_id", table_name="editorial_events")
    op.drop_index("ix_editorial_events_post_id", table_name="editorial_events")
    op.drop_table("editorial_events")

    op.drop_index("ix_posts_editorial_status", table_name="posts")
    op.drop_index("ix_posts_publication_id", table_name="posts")
    op.drop_constraint("ck_posts_editorial_status", "posts", type_="check")
    op.drop_constraint(
        "fk_posts_publication_id_publications", "posts", type_="foreignkey"
    )
    op.drop_column("posts", "editorial_status")
    op.drop_column("posts", "publication_id")

    op.drop_index(
        "ix_publication_audit_logs_created_at", table_name="publication_audit_logs"
    )
    op.drop_index(
        "ix_publication_audit_logs_target_user_id", table_name="publication_audit_logs"
    )
    op.drop_index(
        "ix_publication_audit_logs_actor_id", table_name="publication_audit_logs"
    )
    op.drop_index(
        "ix_publication_audit_logs_publication_id", table_name="publication_audit_logs"
    )
    op.drop_table("publication_audit_logs")

    op.drop_index(
        "uq_publication_invitations_pending_email",
        table_name="publication_invitations",
    )
    op.drop_index(
        "ix_publication_invitations_expires_at", table_name="publication_invitations"
    )
    op.drop_index(
        "ix_publication_invitations_status", table_name="publication_invitations"
    )
    op.drop_index(
        "ix_publication_invitations_invited_by_id", table_name="publication_invitations"
    )
    op.drop_index(
        "ix_publication_invitations_token_hash", table_name="publication_invitations"
    )
    op.drop_index(
        "ix_publication_invitations_email_key", table_name="publication_invitations"
    )
    op.drop_index(
        "ix_publication_invitations_publication_id", table_name="publication_invitations"
    )
    op.drop_table("publication_invitations")

    op.drop_index(
        "uq_publication_memberships_one_owner", table_name="publication_memberships"
    )
    op.drop_index(
        "ix_publication_memberships_status", table_name="publication_memberships"
    )
    op.drop_index(
        "ix_publication_memberships_user_id", table_name="publication_memberships"
    )
    op.drop_index(
        "ix_publication_memberships_publication_id",
        table_name="publication_memberships",
    )
    op.drop_table("publication_memberships")

    op.drop_index("ix_publications_deleted_at", table_name="publications")
    op.drop_index("ix_publications_status", table_name="publications")
    op.drop_index("ix_publications_visibility", table_name="publications")
    op.drop_index("ix_publications_owner_id", table_name="publications")
    op.drop_index("ix_publications_cover_media_id", table_name="publications")
    op.drop_index("ix_publications_logo_media_id", table_name="publications")
    op.drop_index("ix_publications_slug", table_name="publications")
    op.drop_table("publications")
