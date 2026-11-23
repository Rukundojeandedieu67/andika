"""Add notifications, preferences, and the email outbox."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f8b1d4c62a90"
down_revision: str | None = "e3c8a1d74b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EVENTS = (
    "comment_received",
    "comment_reply_received",
    "comment_approved",
    "comment_hidden",
    "comment_rejected",
    "publication_invitation_received",
    "publication_invitation_accepted",
    "publication_member_role_changed",
    "publication_member_suspended",
    "publication_member_removed",
    "publication_ownership_transferred",
    "article_submitted_for_review",
    "article_review_started",
    "article_changes_requested",
    "article_approved",
    "article_published",
    "article_unpublished",
)
_DELIVERY = ("pending", "sending", "sent", "failed", "not_configured")


def upgrade() -> None:
    """Add private notifications and the delivery queue."""

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("action_url", sa.String(length=300), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("in_app", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN (" + ", ".join(repr(value) for value in _EVENTS) + ")",
            name="type",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_actor_id", "notifications", ["actor_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index(
        "ix_notifications_recipient_id_created_at",
        "notifications",
        ["recipient_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_recipient_id_is_read",
        "notifications",
        ["recipient_id", "is_read"],
    )
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("in_app_comments", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_comments", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("in_app_publications", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_publications", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("in_app_editorial", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_editorial", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("in_app_account", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_account", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN (" + ", ".join(repr(value) for value in _DELIVERY) + ")",
            name="status",
        ),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id"),
    )
    op.create_index(
        "ix_notification_deliveries_status", "notification_deliveries", ["status"]
    )
    op.create_index(
        "ix_notification_deliveries_next_attempt_at",
        "notification_deliveries",
        ["next_attempt_at"],
    )
    op.create_index(
        "ix_notification_deliveries_status_next_attempt_at",
        "notification_deliveries",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    """Remove notification tables."""

    op.drop_index(
        "ix_notification_deliveries_status_next_attempt_at",
        table_name="notification_deliveries",
    )
    op.drop_index(
        "ix_notification_deliveries_next_attempt_at", table_name="notification_deliveries"
    )
    op.drop_index("ix_notification_deliveries_status", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_recipient_id_is_read", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id_created_at", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_actor_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")
