"""Reports filed against comments."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UtcDateTime
from app.models.comment import Comment
from app.models.user import User


class ReportReason(str, enum.Enum):
    """Why a reader asked for a comment to be reviewed."""

    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    MISINFORMATION = "misinformation"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    """Review state. Reporting a comment does not delete it."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class CommentReport(Base):
    """One user's report of one comment. A second report from the same user is rejected."""

    __tablename__ = "comment_reports"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('spam', 'harassment', 'hate_speech', 'misinformation', "
            "'inappropriate_content', 'other')",
            name="reason",
        ),
        CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="status",
        ),
        UniqueConstraint(
            "comment_id",
            "reporter_id",
            name="uq_comment_reports_comment_id_reporter_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    comment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[ReportReason] = mapped_column(
        Enum(
            ReportReason,
            name="report_reason",
            native_enum=False,
            length=32,
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ReportStatus] = mapped_column(
        Enum(
            ReportStatus,
            name="report_status",
            native_enum=False,
            length=16,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=ReportStatus.OPEN,
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    comment: Mapped[Comment] = relationship()
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by])
