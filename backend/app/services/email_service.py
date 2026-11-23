"""SMTP email delivery, kept separate from authentication decisions."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from enum import Enum
from pathlib import Path
from uuid import uuid4

from app.core.config import BACKEND_ROOT, Settings, get_settings

logger = logging.getLogger(__name__)


class EmailStatus(str, Enum):
    SENT = "sent"
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True)
class EmailResult:
    status: EmailStatus
    template: str


class EmailService:
    """Send authentication email. A missing SMTP setup is reported, not hidden."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def can_deliver(self) -> bool:
        return self._settings.email_delivery_configured

    def send_verification(
        self, *, recipient: str, token: str, expires_at: datetime
    ) -> EmailResult:
        link = f"{self._settings.public_app_url}/verify-email#token={token}"
        body = (
            "Confirm your ANDIKA email address.\n\n"
            f"Open this link: {link}\n\n"
            "The token is in the URL fragment so it is not sent to the server as a "
            "query parameter. The link expires at "
            f"{expires_at.isoformat()}.\n\n"
            "If you did not create an ANDIKA account, you can ignore this message."
        )
        return self._send(
            template="email_verification",
            recipient=recipient,
            subject="Verify your ANDIKA email",
            body=body,
        )

    def send_password_reset(
        self, *, recipient: str, token: str, expires_at: datetime
    ) -> EmailResult:
        link = f"{self._settings.public_app_url}/reset-password#token={token}"
        body = (
            "A password reset was requested for your ANDIKA account.\n\n"
            f"Open this link: {link}\n\n"
            "The token is in the URL fragment so it is not sent to the server as a "
            "query parameter. The link expires at "
            f"{expires_at.isoformat()} and can be used once.\n\n"
            "If you did not request a reset, you can ignore this message."
        )
        return self._send(
            template="password_reset",
            recipient=recipient,
            subject="Reset your ANDIKA password",
            body=body,
        )

    def send_publication_invitation(
        self,
        *,
        recipient: str,
        token: str,
        publication_name: str,
        expires_at: datetime,
    ) -> EmailResult:
        link = f"{self._settings.public_app_url}/invitations/accept#token={token}"
        body = (
            f"You have been invited to join {publication_name} on ANDIKA.\n\n"
            f"Open this link: {link}\n\n"
            "The token is in the URL fragment so it is not sent to the server as a "
            "query parameter. The link expires at "
            f"{expires_at.isoformat()} and can be used once.\n\n"
            "If you were not expecting this invitation, you can ignore this message."
        )
        return self._send(
            template="publication_invitation",
            recipient=recipient,
            subject=f"Join {publication_name} on ANDIKA",
            body=body,
        )

    def send_password_changed(self, *, recipient: str) -> EmailResult:
        body = (
            "The password for your ANDIKA account was changed.\n\n"
            "If you did not make this change, reset your password and contact support."
        )
        return self._send(
            template="password_changed",
            recipient=recipient,
            subject="Your ANDIKA password was changed",
            body=body,
        )

    def _send(
        self, *, template: str, recipient: str, subject: str, body: str
    ) -> EmailResult:
        if not self.can_deliver:
            self._save_development_copy(
                template=template, recipient=recipient, subject=subject, body=body
            )
            logger.warning(
                "Email was not sent because SMTP is not configured: %s", template
            )
            return EmailResult(status=EmailStatus.NOT_CONFIGURED, template=template)
        message = EmailMessage()
        message["From"] = self._settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=10,
            ) as client:
                if self._settings.smtp_use_tls:
                    client.starttls()
                if self._settings.smtp_username:
                    client.login(
                        self._settings.smtp_username, self._settings.smtp_password
                    )
                client.send_message(message)
        except OSError as exc:
            logger.warning(
                "Email delivery failed for %s: %s", template, type(exc).__name__
            )
            return EmailResult(status=EmailStatus.FAILED, template=template)
        except smtplib.SMTPRecipientsRefused:
            logger.warning("Email delivery rejected recipients for %s", template)
            return EmailResult(status=EmailStatus.PERMANENT_FAILURE, template=template)
        except smtplib.SMTPException as exc:
            logger.warning(
                "Email delivery failed for %s: %s", template, type(exc).__name__
            )
            return EmailResult(status=EmailStatus.FAILED, template=template)
        logger.info("Email sent: %s", template)
        return EmailResult(status=EmailStatus.SENT, template=template)

    def send_notification(self, *, recipient: str, subject: str, body: str) -> EmailResult:
        """Send one notification email through the same SMTP path as account mail."""

        return self._send(
            template="notification",
            recipient=recipient,
            subject=subject,
            body=body,
        )

    def _save_development_copy(
        self, *, template: str, recipient: str, subject: str, body: str
    ) -> None:
        """Keep a local copy during development without treating it as delivery."""

        directory = self._outbox_directory()
        if directory is None:
            return
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{template}-{uuid4().hex}.txt"
        path = directory / filename
        path.write_text(
            f"To: {recipient}\nSubject: {subject}\n\n{body}\n",
            encoding="utf-8",
        )
        logger.info("Saved undelivered %s email for local inspection", template)

    def _outbox_directory(self) -> Path | None:
        if self._settings.environment != "development":
            return None
        return BACKEND_ROOT / "var" / "mail"


def get_email_service() -> EmailService:
    """Build an email service from the current settings."""

    return EmailService(get_settings())
