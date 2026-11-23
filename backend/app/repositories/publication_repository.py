"""Queries for publications, members, invitations, and audit rows."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.editorial import EditorialEvent
from app.models.media import Media
from app.models.publication import (
    InvitationStatus,
    MembershipStatus,
    Publication,
    PublicationAuditLog,
    PublicationInvitation,
    PublicationMembership,
    PublicationStatus,
    PublicationVisibility,
)


def _like(value: str) -> str:
    term = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{term}%"


class PublicationRepository:
    """Read and write publications without applying permission rules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, publication: Publication) -> Publication:
        self.session.add(publication)
        self.session.flush()
        return publication

    def get(self, publication_id: uuid.UUID, *, lock: bool = False) -> Publication | None:
        statement = select(Publication).where(Publication.id == publication_id)
        if lock and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_loaded(self, publication_id: uuid.UUID) -> Publication | None:
        return self.session.scalar(
            select(Publication)
            .options(*self._profile_options())
            .where(Publication.id == publication_id, Publication.deleted_at.is_(None))
        )

    def get_by_slug(self, slug: str) -> Publication | None:
        return self.session.scalar(
            select(Publication)
            .options(*self._profile_options())
            .where(Publication.slug == slug, Publication.deleted_at.is_(None))
        )

    def slug_in_use(self, slug: str, *, excluding: uuid.UUID | None = None) -> bool:
        found = self.session.scalar(select(Publication.id).where(Publication.slug == slug))
        return found is not None and found != excluding

    def page_public(
        self, *, page: int, page_size: int, search: str | None
    ) -> tuple[list[Publication], int]:
        clauses: list[ColumnElement[bool]] = [
            Publication.deleted_at.is_(None),
            Publication.status == PublicationStatus.ACTIVE,
            Publication.visibility == PublicationVisibility.PUBLIC,
        ]
        if search:
            pattern = _like(search.strip())
            clauses.append(
                or_(
                    Publication.name.ilike(pattern, escape="\\"),
                    Publication.description.ilike(pattern, escape="\\"),
                )
            )
        return self._page(clauses, page, page_size)

    def page_for_member(
        self, user_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[tuple[Publication, PublicationMembership]], int]:
        clauses = [
            PublicationMembership.user_id == user_id,
            PublicationMembership.status == MembershipStatus.ACTIVE,
            Publication.deleted_at.is_(None),
        ]
        total = self.session.scalar(
            select(func.count(Publication.id))
            .join(
                PublicationMembership,
                PublicationMembership.publication_id == Publication.id,
            )
            .where(*clauses)
        )
        rows = self.session.execute(
            select(Publication, PublicationMembership)
            .join(
                PublicationMembership,
                PublicationMembership.publication_id == Publication.id,
            )
            .where(*clauses)
            .order_by(Publication.name.asc(), Publication.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(publication, membership) for publication, membership in rows], int(total or 0)

    def _page(
        self, clauses: list[ColumnElement[bool]], page: int, page_size: int
    ) -> tuple[list[Publication], int]:
        total = self.session.scalar(select(func.count(Publication.id)).where(*clauses))
        rows = (
            self.session.scalars(
                select(Publication)
                .options(*self._profile_options())
                .where(*clauses)
                .order_by(Publication.created_at.desc(), Publication.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return list(rows), int(total or 0)

    def _profile_options(self) -> tuple[object, ...]:
        return (
            joinedload(Publication.owner),
            selectinload(Publication.logo_media).selectinload(Media.variants),
            selectinload(Publication.cover_media).selectinload(Media.variants),
        )


class MembershipRepository:
    """One row per user and publication."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, membership: PublicationMembership) -> PublicationMembership:
        self.session.add(membership)
        self.session.flush()
        return membership

    def get(self, membership_id: uuid.UUID) -> PublicationMembership | None:
        return self.session.scalar(
            select(PublicationMembership)
            .options(joinedload(PublicationMembership.user))
            .where(PublicationMembership.id == membership_id)
        )

    def for_user(
        self, publication_id: uuid.UUID, user_id: uuid.UUID
    ) -> PublicationMembership | None:
        return self.session.scalar(
            select(PublicationMembership).where(
                PublicationMembership.publication_id == publication_id,
                PublicationMembership.user_id == user_id,
            )
        )

    def page(
        self,
        publication_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        include_inactive: bool,
    ) -> tuple[list[PublicationMembership], int]:
        clauses: list[ColumnElement[bool]] = [
            PublicationMembership.publication_id == publication_id
        ]
        if not include_inactive:
            clauses.append(PublicationMembership.status == MembershipStatus.ACTIVE)
        total = self.session.scalar(
            select(func.count(PublicationMembership.id)).where(*clauses)
        )
        rows = (
            self.session.scalars(
                select(PublicationMembership)
                .options(joinedload(PublicationMembership.user))
                .where(*clauses)
                .order_by(PublicationMembership.joined_at.asc(), PublicationMembership.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return list(rows), int(total or 0)

    def count(self, publication_id: uuid.UUID) -> int:
        total = self.session.scalar(
            select(func.count(PublicationMembership.id)).where(
                PublicationMembership.publication_id == publication_id,
                PublicationMembership.status == MembershipStatus.ACTIVE,
            )
        )
        return int(total or 0)


class InvitationRepository:
    """Hashed invitation tokens."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, invitation: PublicationInvitation) -> PublicationInvitation:
        self.session.add(invitation)
        self.session.flush()
        return invitation

    def get(self, invitation_id: uuid.UUID, *, lock: bool = False) -> PublicationInvitation | None:
        statement = select(PublicationInvitation).where(PublicationInvitation.id == invitation_id)
        if lock and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        invitation = self.session.scalar(statement)
        return invitation

    def get_by_hash(self, token_hash: str, *, lock: bool = False) -> PublicationInvitation | None:
        statement = select(PublicationInvitation).where(
            PublicationInvitation.token_hash == token_hash
        )
        if lock and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def pending_for_email(
        self, publication_id: uuid.UUID, email_key: str
    ) -> PublicationInvitation | None:
        return self.session.scalar(
            select(PublicationInvitation).where(
                PublicationInvitation.publication_id == publication_id,
                PublicationInvitation.email_key == email_key,
                PublicationInvitation.status == InvitationStatus.PENDING,
            )
        )

    def expire_due(self, publication_id: uuid.UUID, now: datetime) -> None:
        rows = self.session.scalars(
            select(PublicationInvitation).where(
                PublicationInvitation.publication_id == publication_id,
                PublicationInvitation.status == InvitationStatus.PENDING,
                PublicationInvitation.expires_at <= now,
            )
        ).all()
        for invitation in rows:
            invitation.status = InvitationStatus.EXPIRED
        if rows:
            self.session.flush()

    def page(
        self, publication_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[PublicationInvitation], int]:
        clauses = [PublicationInvitation.publication_id == publication_id]
        total = self.session.scalar(
            select(func.count(PublicationInvitation.id)).where(*clauses)
        )
        rows = (
            self.session.scalars(
                select(PublicationInvitation)
                .options(joinedload(PublicationInvitation.invited_by))
                .where(*clauses)
                .order_by(PublicationInvitation.created_at.desc(), PublicationInvitation.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return list(rows), int(total or 0)


class PublicationAuditRepository:
    """Append-only publication history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entry: PublicationAuditLog) -> PublicationAuditLog:
        self.session.add(entry)
        self.session.flush()
        return entry

    def page(
        self, publication_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[PublicationAuditLog], int]:
        clauses = [PublicationAuditLog.publication_id == publication_id]
        total = self.session.scalar(select(func.count(PublicationAuditLog.id)).where(*clauses))
        rows = (
            self.session.scalars(
                select(PublicationAuditLog)
                .options(
                    joinedload(PublicationAuditLog.actor),
                    joinedload(PublicationAuditLog.target),
                )
                .where(*clauses)
                .order_by(PublicationAuditLog.created_at.desc(), PublicationAuditLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return list(rows), int(total or 0)


class EditorialEventRepository:
    """Append-only editorial transitions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: EditorialEvent) -> EditorialEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def for_post(self, post_id: uuid.UUID) -> list[EditorialEvent]:
        rows = (
            self.session.scalars(
                select(EditorialEvent)
                .options(joinedload(EditorialEvent.actor))
                .where(EditorialEvent.post_id == post_id)
                .order_by(EditorialEvent.created_at.asc(), EditorialEvent.id.asc())
            )
            .unique()
            .all()
        )
        return list(rows)
