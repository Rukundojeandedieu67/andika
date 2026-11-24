"""Add direct-message conversations.

Revision ID: b3e7a1c94d02
Revises: a9d4c2e81b37
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3e7a1c94d02"
down_revision: str | None = "a9d4c2e81b37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store one thread per pair of accounts and the messages in that thread."""

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_low_id", sa.Uuid(), nullable=False),
        sa.Column("user_high_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_low_id"], ["users.id"], name="fk_conversations_user_low_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_high_id"],
            ["users.id"],
            name="fk_conversations_user_high_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_conversations_pair"),
        sa.CheckConstraint("user_low_id <> user_high_id", name="pair"),
    )
    op.create_index("ix_conversations_user_low_id", "conversations", ["user_low_id"])
    op.create_index("ix_conversations_user_high_id", "conversations", ["user_high_id"])
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_chat_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["users.id"], name="fk_chat_messages_sender_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"])
    op.create_index(
        "ix_chat_messages_conversation_id_created_at",
        "chat_messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    """Remove direct messages. Accounts and articles stay."""

    op.drop_index("ix_chat_messages_conversation_id_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_sender_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_conversations_updated_at", table_name="conversations")
    op.drop_index("ix_conversations_user_high_id", table_name="conversations")
    op.drop_index("ix_conversations_user_low_id", table_name="conversations")
    op.drop_table("conversations")
