"""Article-author and administrator moderation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.comment import Comment, CommentStatus
from app.models.comment_report import CommentReport, ReportStatus
from app.models.moderation_log import ModerationLog
from app.models.post import Post
from app.models.user import User
from app.repositories.comment_report_repository import CommentReportRepository
from app.repositories.comment_repository import CommentRepository
from app.repositories.moderation_repository import ModerationRepository
from app.services.exceptions import ConflictError, NotFoundError, ServiceError

_AUTHOR_TRANSITIONS = {
    (CommentStatus.PENDING, CommentStatus.APPROVED),
    (CommentStatus.PENDING, CommentStatus.HIDDEN),
    (CommentStatus.APPROVED, CommentStatus.HIDDEN),
    (CommentStatus.HIDDEN, CommentStatus.APPROVED),
}
_ADMIN_TRANSITIONS = _AUTHOR_TRANSITIONS | {
    (CommentStatus.PENDING, CommentStatus.REJECTED),
    (CommentStatus.APPROVED, CommentStatus.REJECTED),
    (CommentStatus.HIDDEN, CommentStatus.REJECTED),
    (CommentStatus.REJECTED, CommentStatus.APPROVED),
    (CommentStatus.REJECTED, CommentStatus.HIDDEN),
}


def moderate_for_author(
    session: Session,
    *,
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    actor: User,
    status: CommentStatus,
    reason: str | None,
) -> Comment:
    """Apply a decision the article author is allowed to make."""

    post = _authored_post(session, post_id, actor)
    comment = _comment_on_post(session, comment_id, post.id, lock=True)
    return _change_status(
        session,
        comment,
        actor,
        status,
        reason,
        allowed=_AUTHOR_TRANSITIONS,
    )


def moderate_for_admin(
    session: Session,
    *,
    comment_id: uuid.UUID,
    actor: User,
    status: CommentStatus,
    reason: str | None,
) -> Comment:
    """Apply an administrator decision and record it."""

    comment = CommentRepository(session).get(comment_id, lock=True)
    if comment is None:
        raise NotFoundError("Comment not found.")
    return _change_status(
        session,
        comment,
        actor,
        status,
        reason,
        allowed=_ADMIN_TRANSITIONS,
    )


def create_report(
    session: Session,
    *,
    comment_id: uuid.UUID,
    reporter: User,
    reason: object,
    description: str | None,
) -> CommentReport:
    """Record a report. The comment stays in place until a moderator decides."""

    comment = CommentRepository(session).get(comment_id)
    if (
        comment is None
        or comment.deleted_at is not None
        or comment.status is not CommentStatus.APPROVED
    ):
        raise NotFoundError("Comment not found.")
    reports = CommentReportRepository(session)
    if reports.find_existing(comment.id, reporter.id) is not None:
        raise ConflictError("You have already reported that comment.")
    report = CommentReport(
        comment_id=comment.id,
        reporter_id=reporter.id,
        reason=reason,
        description=description,
        status=ReportStatus.OPEN,
        reporter=reporter,
    )
    try:
        return reports.add(report)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("You have already reported that comment.") from exc


def review_report(
    session: Session,
    *,
    report_id: uuid.UUID,
    actor: User,
    status: ReportStatus,
    post_id: uuid.UUID | None = None,
) -> CommentReport:
    """Resolve or dismiss a report without deleting the comment."""

    report = CommentReportRepository(session).get(report_id)
    if report is None:
        raise NotFoundError("Report not found.")
    if post_id is not None:
        _authored_post(session, post_id, actor)
        if report.comment.post_id != post_id:
            raise NotFoundError("Report not found.")
    if report.status is not ReportStatus.OPEN:
        raise ConflictError("That report has already been reviewed.")
    now = datetime.now(UTC)
    report.status = status
    report.reviewed_by = actor.id
    report.reviewed_at = now
    session.flush()
    return report


def _change_status(
    session: Session,
    comment: Comment,
    actor: User,
    status: CommentStatus,
    reason: str | None,
    *,
    allowed: set[tuple[CommentStatus, CommentStatus]],
) -> Comment:
    if comment.status is status:
        raise ConflictError("The comment is already in that state.")
    if (comment.status, status) not in allowed:
        raise ServiceError("You do not have permission to perform this action.", 403)
    previous = comment.status
    comment.status = status
    comment.updated_at = datetime.now(UTC)
    entry = ModerationRepository(session).add(
        ModerationLog(
            moderator_id=actor.id,
            comment_id=comment.id,
            action=_action(previous, status),
            previous_status=previous.value,
            new_status=status.value,
            reason=reason,
        )
    )
    session.flush()
    from app.services.notification_events import comment_moderated

    comment_moderated(
        session,
        comment_author_id=comment.author_id,
        actor=actor,
        post_id=comment.post_id,
        status_value=status.value,
        log_id=entry.id,
    )
    if comment.author is None:
        session.refresh(comment)
    return comment


def _action(previous: CommentStatus, new: CommentStatus) -> str:
    if new is CommentStatus.HIDDEN:
        return "hide"
    if new is CommentStatus.REJECTED:
        return "reject"
    if previous is CommentStatus.HIDDEN and new is CommentStatus.APPROVED:
        return "restore"
    return "approve"


def require_article_author(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    """Return the article when the caller wrote it."""

    return _authored_post(session, post_id, actor)


def _authored_post(session: Session, post_id: uuid.UUID, actor: User) -> Post:
    post = session.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise NotFoundError()
    if post.author_id != actor.id:
        raise ServiceError("You do not have permission to perform this action.", 403)
    return post


def _comment_on_post(
    session: Session, comment_id: uuid.UUID, post_id: uuid.UUID, *, lock: bool
) -> Comment:
    comment = CommentRepository(session).get(comment_id, lock=lock)
    if comment is None or comment.post_id != post_id:
        raise NotFoundError("Comment not found.")
    return comment
