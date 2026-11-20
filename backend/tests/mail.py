"""Test double that records email instead of contacting an SMTP server."""

from app.core.config import Settings
from app.services.email_service import EmailResult, EmailService, EmailStatus


class RecordingEmailService(EmailService):
    """Capture messages so tests can read one-time tokens without an inbox."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.messages: list[dict[str, str]] = []

    @property
    def can_deliver(self) -> bool:
        return True

    def _send(
        self, *, template: str, recipient: str, subject: str, body: str
    ) -> EmailResult:
        self.messages.append(
            {
                "template": template,
                "recipient": recipient,
                "subject": subject,
                "body": body,
            }
        )
        return EmailResult(status=EmailStatus.SENT, template=template)
