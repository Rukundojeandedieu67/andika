"""Registration, login, refresh tokens, and account recovery."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    dummy_password_hash,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    validate_new_password,
    verify_password,
)
from app.database.types import ensure_utc
from app.models.auth_session import AuthSession
from app.models.auth_token import EmailVerificationToken, PasswordResetToken
from app.models.user import User, UserRole
from app.repositories.auth_session_repository import (
    AuthSessionRepository,
    EmailVerificationRepository,
    PasswordResetRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.email_service import EmailService
from app.services.exceptions import ConflictError, ServiceError, UnauthorizedError

logger = logging.getLogger(__name__)

_INVALID_CREDENTIALS = "Invalid email or password."
_INVALID_REFRESH = "Authentication is invalid."
_INVALID_RESET = "The reset token is invalid or expired."
_INVALID_VERIFICATION = "The verification token is invalid or expired."


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


def register_user(
    session: Session, payload: RegisterRequest, mail: EmailService
) -> User:
    """Create a reader account and issue an email-verification token."""

    users = UserRepository(session)
    if users.get_by_username_key(payload.username) is not None:
        raise ConflictError("That username is already in use.")
    if users.get_by_email(str(payload.email)) is not None:
        raise ConflictError("That email address is already in use.")

    user = User(
        username=payload.username,
        username_key=payload.username.casefold(),
        email=str(payload.email).casefold(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.READER,
        is_active=True,
        is_verified=False,
    )
    try:
        users.add(user)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "That username or email address is already in use."
        ) from exc

    _issue_verification_token(session, user, mail)
    logger.info("Registered user %s", user.id)
    return user


def authenticate_user(
    session: Session,
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedTokens:
    """Verify credentials and issue a short-lived access token plus a refresh session."""

    users = UserRepository(session)
    user = users.get_by_email(email)
    password_hash = user.hashed_password if user is not None else dummy_password_hash()
    password_matches = verify_password(password, password_hash)
    if user is None or not password_matches or not user.is_active:
        raise UnauthorizedError(_INVALID_CREDENTIALS)

    user.last_login_at = datetime.now(UTC)
    user.updated_at = user.last_login_at
    issued = _issue_tokens(
        session,
        user,
        family_id=uuid.uuid4(),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    logger.info("Login succeeded for user %s", user.id)
    return issued


def refresh_session(
    session: Session,
    *,
    refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedTokens:
    """Rotate a refresh token. Reuse of a revoked token revokes the whole family."""

    repositories = AuthSessionRepository(session)
    current = repositories.get_by_token_hash(hash_opaque_token(refresh_token))
    now = datetime.now(UTC)
    if current is None:
        raise UnauthorizedError(_INVALID_REFRESH)
    if current.revoked_at is not None or current.replaced_by_session_id is not None:
        repositories.revoke_family(current.family_id, when=now)
        session.commit()
        logger.warning(
            "Refresh token reuse detected for session family %s", current.family_id
        )
        raise UnauthorizedError(_INVALID_REFRESH)
    if _as_utc(current.expires_at) <= now:
        current.revoked_at = now
        session.commit()
        raise UnauthorizedError(_INVALID_REFRESH)

    user = UserRepository(session).get_by_id(current.user_id)
    if user is None or not user.is_active:
        repositories.revoke_family(current.family_id, when=now)
        session.commit()
        raise UnauthorizedError(_INVALID_REFRESH)

    issued = _issue_tokens(
        session,
        user,
        family_id=current.family_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    current.revoked_at = now
    current.replaced_by_session_id = _session_id_from_access_token(issued.access_token)
    logger.info("Rotated refresh session for user %s", user.id)
    return issued


def logout_session(session: Session, *, user_id: uuid.UUID, refresh_token: str) -> None:
    """Revoke the refresh session that belongs to the authenticated user."""

    repositories = AuthSessionRepository(session)
    current = repositories.get_by_token_hash(hash_opaque_token(refresh_token))
    if current is None or current.user_id != user_id or current.revoked_at is not None:
        raise UnauthorizedError(_INVALID_REFRESH)
    now = datetime.now(UTC)
    current.revoked_at = now
    repositories.revoke_family(current.family_id, when=now)
    logger.info("Revoked refresh session family %s", current.family_id)


def request_password_reset(session: Session, *, email: str, mail: EmailService) -> None:
    """Store a hashed reset token when the account exists. The caller stays generic."""

    user = UserRepository(session).get_by_email(email)
    if user is None or not user.is_active:
        return
    settings = get_settings()
    now = datetime.now(UTC)
    PasswordResetRepository(session).cancel_outstanding(user.id, when=now)
    raw_token = generate_opaque_token()
    expires_at = now + timedelta(minutes=settings.password_reset_token_expire_minutes)
    PasswordResetRepository(session).add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=expires_at,
        )
    )
    mail.send_password_reset(
        recipient=user.email, token=raw_token, expires_at=expires_at
    )
    logger.info("Password reset requested for user %s", user.id)


def reset_password(
    session: Session, *, token: str, password: str, mail: EmailService
) -> None:
    """Consume a reset token, replace the password, and revoke refresh sessions."""

    record = PasswordResetRepository(session).get_by_hash(hash_opaque_token(token))
    now = datetime.now(UTC)
    if (
        record is None
        or record.used_at is not None
        or _as_utc(record.expires_at) <= now
    ):
        raise ServiceError(_INVALID_RESET)

    user = UserRepository(session).get_by_id(record.user_id)
    if user is None or not user.is_active:
        raise ServiceError(_INVALID_RESET)
    validate_new_password(password, username=user.username, email=user.email)
    if verify_password(password, user.hashed_password):
        raise ServiceError("Choose a different password.")

    user.hashed_password = hash_password(password)
    user.updated_at = now
    record.used_at = now
    AuthSessionRepository(session).revoke_all_for_user(user.id, when=now)
    mail.send_password_changed(recipient=user.email)
    logger.info("Password reset completed for user %s", user.id)


def verify_email(session: Session, *, token: str) -> User:
    """Mark the account verified when the token is unused and unexpired."""

    record = EmailVerificationRepository(session).get_by_hash(hash_opaque_token(token))
    now = datetime.now(UTC)
    if (
        record is None
        or record.used_at is not None
        or _as_utc(record.expires_at) <= now
    ):
        raise ServiceError(_INVALID_VERIFICATION)
    user = UserRepository(session).get_by_id(record.user_id)
    if user is None or not user.is_active:
        raise ServiceError(_INVALID_VERIFICATION)
    record.used_at = now
    EmailVerificationRepository(session).cancel_outstanding(user.id, when=now)
    user.is_verified = True
    user.updated_at = now
    logger.info("Verified email for user %s", user.id)
    return user


def resend_verification(session: Session, *, email: str, mail: EmailService) -> None:
    """Issue a new verification token, subject to a short cooldown."""

    user = UserRepository(session).get_by_email(email)
    if user is None or not user.is_active or user.is_verified:
        return
    settings = get_settings()
    now = datetime.now(UTC)
    latest = EmailVerificationRepository(session).latest_unused(user.id)
    if latest is not None:
        age = (now - _as_utc(latest.created_at)).total_seconds()
        if age < settings.verification_resend_cooldown_seconds:
            logger.info(
                "Verification resend suppressed by cooldown for user %s", user.id
            )
            return
    _issue_verification_token(session, user, mail)
    logger.info("Verification resend issued for user %s", user.id)


def _issue_verification_token(session: Session, user: User, mail: EmailService) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    EmailVerificationRepository(session).cancel_outstanding(user.id, when=now)
    raw_token = generate_opaque_token()
    expires_at = now + timedelta(hours=settings.email_verification_token_expire_hours)
    EmailVerificationRepository(session).add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=expires_at,
        )
    )
    mail.send_verification(recipient=user.email, token=raw_token, expires_at=expires_at)


def _issue_tokens(
    session: Session,
    user: User,
    *,
    family_id: uuid.UUID,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedTokens:
    settings = get_settings()
    now = datetime.now(UTC)
    raw_refresh = generate_opaque_token()
    auth_session = AuthSession(
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_opaque_token(raw_refresh),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    AuthSessionRepository(session).add(auth_session)
    access_token = create_access_token(
        str(user.id),
        additional_claims={"sid": str(auth_session.id)},
    )
    return IssuedTokens(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


def _session_id_from_access_token(token: str) -> uuid.UUID | None:
    from app.core.security import decode_access_token

    payload = decode_access_token(token)
    sid = payload.get("sid")
    if not isinstance(sid, str):
        return None
    try:
        return uuid.UUID(sid)
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    return ensure_utc(value)
