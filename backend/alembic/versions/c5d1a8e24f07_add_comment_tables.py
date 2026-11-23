"""Add comments, reports, and moderation history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c5d1a8e24f07"
down_revision: str | None = "f4b8d2e91c36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add discussion tables without changing existing article rows."""

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'hidden', 'rejected')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_comments_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_comments_author_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["comments.id"],
            name="fk_comments_parent_id_comments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_comments"),
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_status", "comments", ["status"])
    op.create_index("ix_comments_created_at", "comments", ["created_at"])
    op.create_index("ix_comments_deleted_at", "comments", ["deleted_at"])
    op.create_index(
        "ix_comments_post_id_created_at", "comments", ["post_id", "created_at"]
    )

    op.create_table(
        "comment_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason IN ('spam', 'harassment', 'hate_speech', 'misinformation', "
            "'inappropriate_content', 'other')",
            name="reason",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comments.id"],
            name="fk_comment_reports_comment_id_comments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            name="fk_comment_reports_reporter_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name="fk_comment_reports_reviewed_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_comment_reports"),
        sa.UniqueConstraint(
            "comment_id",
            "reporter_id",
            name="uq_comment_reports_comment_id_reporter_id",
        ),
    )
    op.create_index("ix_comment_reports_comment_id", "comment_reports", ["comment_id"])
    op.create_index("ix_comment_reports_reporter_id", "comment_reports", ["reporter_id"])
    op.create_index("ix_comment_reports_status", "comment_reports", ["status"])
    op.create_index("ix_comment_reports_reviewed_by", "comment_reports", ["reviewed_by"])
    op.create_index("ix_comment_reports_created_at", "comment_reports", ["created_at"])

    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("moderator_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=False),
        sa.Column("new_status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["moderator_id"],
            ["users.id"],
            name="fk_moderation_logs_moderator_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comments.id"],
            name="fk_moderation_logs_comment_id_comments",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_logs"),
    )
    op.create_index("ix_moderation_logs_moderator_id", "moderation_logs", ["moderator_id"])
    op.create_index("ix_moderation_logs_comment_id", "moderation_logs", ["comment_id"])
    op.create_index("ix_moderation_logs_created_at", "moderation_logs", ["created_at"])


def downgrade() -> None:
    """Remove discussion tables. Articles and accounts stay in place."""

    op.drop_index("ix_moderation_logs_created_at", table_name="moderation_logs")
    op.drop_index("ix_moderation_logs_comment_id", table_name="moderation_logs")
    op.drop_index("ix_moderation_logs_moderator_id", table_name="moderation_logs")
    op.drop_table("moderation_logs")
    op.drop_index("ix_comment_reports_created_at", table_name="comment_reports")
    op.drop_index("ix_comment_reports_reviewed_by", table_name="comment_reports")
    op.drop_index("ix_comment_reports_status", table_name="comment_reports")
    op.drop_index("ix_comment_reports_reporter_id", table_name="comment_reports")
    op.drop_index("ix_comment_reports_comment_id", table_name="comment_reports")
    op.drop_table("comment_reports")
    op.drop_index("ix_comments_post_id_created_at", table_name="comments")
    op.drop_index("ix_comments_deleted_at", table_name="comments")
    op.drop_index("ix_comments_created_at", table_name="comments")
    op.drop_index("ix_comments_status", table_name="comments")
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_table("comments")
