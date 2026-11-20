"""Refresh sessions and one-time authentication tokens."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession
from app.models.auth_token import EmailVerificationToken, PasswordResetToken


class AuthSessionRepository:
    """Persist hashed refresh tokens and revoke session families."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, auth_session: AuthSession) -> AuthSession:
        self.session.add(auth_session)
        self.session.flush()
        return auth_session

    def get_by_id(self, session_id: uuid.UUID) -> AuthSession | None:
        return self.session.get(AuthSession, session_id)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        statement = select(AuthSession).where(AuthSession.token_hash == token_hash)
        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def revoke_family(self, family_id: uuid.UUID, *, when: datetime) -> None:
        rows = self.session.scalars(
            select(AuthSession).where(
                AuthSession.family_id == family_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        for row in rows:
            row.revoked_at = when
        self.session.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID, *, when: datetime) -> None:
        rows = self.session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
        ).all()
        for row in rows:
            row.revoked_at = when
        self.session.flush()


class PasswordResetRepository:
    """Persist hashed password-reset tokens."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        statement = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def cancel_outstanding(self, user_id: uuid.UUID, *, when: datetime) -> None:
        rows = self.session.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
        ).all()
        for row in rows:
            row.used_at = when
        self.session.flush()


class EmailVerificationRepository:
    """Persist hashed email-verification tokens."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: EmailVerificationToken) -> EmailVerificationToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        statement = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def latest_unused(self, user_id: uuid.UUID) -> EmailVerificationToken | None:
        return self.session.scalar(
            select(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.used_at.is_(None),
            )
            .order_by(EmailVerificationToken.created_at.desc())
        )

    def cancel_outstanding(self, user_id: uuid.UUID, *, when: datetime) -> None:
        rows = self.session.scalars(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.used_at.is_(None),
            )
        ).all()
        for row in rows:
            row.used_at = when
        self.session.flush()
