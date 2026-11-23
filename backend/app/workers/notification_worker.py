"""Process notification email jobs independently of the API process.

Run from the backend directory:

    python -m app.workers.notification_worker

The worker polls PostgreSQL, claims a bounded batch, and sends mail only after
the claim transaction commits. SMTP is not held inside that transaction.
A second copy of the worker can run safely: claims use row locks on PostgreSQL.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_session_factory
from app.models.notification import DeliveryStatus, NotificationDelivery
from app.services.email_service import EmailService, EmailStatus, get_email_service

logger = logging.getLogger(__name__)

_STALE_MINUTES = 10
_BACKOFF_CAP_SECONDS = 15 * 60


def process_pending(
    email_service: EmailService | None = None,
    *,
    batch_size: int | None = None,
    max_attempts: int | None = None,
) -> dict[str, int]:
    """Claim and send one batch. Successful jobs are not sent again."""

    settings = get_settings()
    mail = email_service or get_email_service()
    limit = batch_size if batch_size is not None else settings.notification_worker_batch_size
    attempts_limit = (
        max_attempts if max_attempts is not None else settings.notification_email_max_attempts
    )
    now = datetime.now(UTC)
    factory = get_session_factory()
    session = factory()
    try:
        recovered = _recover_stale(session, now)
        claimed = _claim(session, now, limit)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()
    counts = {
        "recovered": recovered,
        "claimed": len(claimed),
        "sent": 0,
        "failed": 0,
        "not_configured": 0,
        "pending": 0,
    }
    for delivery_id, recipient, subject, body in claimed:
        outcome = _send_claimed(
            factory, mail, delivery_id, recipient, subject, body, attempts_limit, now
        )
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def main() -> None:
    """Poll until interrupted. `--once` processes a single batch and exits."""

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    once = "--once" in sys.argv
    while True:
        try:
            stats = process_pending()
            logger.info("Notification batch processed: %s", stats)
        except Exception:
            logger.exception("Notification worker batch failed")
            if once:
                raise
        if once:
            return
        time.sleep(settings.notification_worker_poll_seconds)


def _recover_stale(session: Session, now: datetime) -> int:
    cutoff = now - timedelta(minutes=_STALE_MINUTES)
    rows = session.scalars(
        select(NotificationDelivery).where(
            NotificationDelivery.status == DeliveryStatus.SENDING,
            NotificationDelivery.updated_at < cutoff,
        )
    ).all()
    for row in rows:
        row.updated_at = now
        if row.attempts >= get_settings().notification_email_max_attempts:
            row.status = DeliveryStatus.FAILED
            row.last_error = "stale_claim"
        else:
            row.status = DeliveryStatus.PENDING
            row.next_attempt_at = now
    session.flush()
    return len(rows)


def _claim(session: Session, now: datetime, limit: int) -> list[tuple]:
    statement = (
        select(NotificationDelivery)
        .where(
            NotificationDelivery.status == DeliveryStatus.PENDING,
            NotificationDelivery.next_attempt_at <= now,
        )
        .order_by(NotificationDelivery.created_at.asc())
        .limit(limit)
    )
    if session.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    rows = list(session.scalars(statement).all())
    claimed = []
    for row in rows:
        row.status = DeliveryStatus.SENDING
        row.attempts += 1
        row.updated_at = now
        claimed.append((row.id, row.recipient_email, row.subject, row.body))
    session.flush()
    return claimed


def _send_claimed(factory, mail: EmailService, delivery_id, recipient, subject, body, max_attempts, now):
    result = mail.send_notification(recipient=recipient, subject=subject, body=body)
    session = factory()
    try:
        delivery = session.get(NotificationDelivery, delivery_id)
        if delivery is None or delivery.status is not DeliveryStatus.SENDING:
            session.rollback()
            return "pending"
        delivery.updated_at = datetime.now(UTC)
        if result.status is EmailStatus.SENT:
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = delivery.updated_at
            delivery.last_error = None
            outcome = "sent"
        elif result.status is EmailStatus.NOT_CONFIGURED:
            delivery.status = DeliveryStatus.NOT_CONFIGURED
            delivery.last_error = "not_configured"
            outcome = "not_configured"
        elif result.status is EmailStatus.PERMANENT_FAILURE or delivery.attempts >= max_attempts:
            delivery.status = DeliveryStatus.FAILED
            delivery.last_error = (
                "permanent_failure"
                if result.status is EmailStatus.PERMANENT_FAILURE
                else "temporary_failure"
            )
            outcome = "failed"
        else:
            delivery.status = DeliveryStatus.PENDING
            delay = min(_BACKOFF_CAP_SECONDS, 60 * (2 ** max(delivery.attempts - 1, 0)))
            delivery.next_attempt_at = now + timedelta(seconds=delay)
            delivery.last_error = "temporary_failure"
            outcome = "pending"
        session.commit()
        return outcome
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
