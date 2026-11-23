"""Publication invitations. Raw tokens are emailed and are not stored or returned."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_opaque_token
from app.database.types import ensure_utc
from app.models.publication import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    PublicationInvitation,
    PublicationMembership,
)
from app.models.user import User
from app.repositories.publication_repository import (
    InvitationRepository,
    MembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.publication import InvitationCreate
from app.services.email_service import EmailResult, EmailService
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.publication_access import (
    FORBIDDEN,
    membership_for,
    require_active_member,
    require_active_publication,
    require_editor,
    require_publication,
)
from app.services.publication_service import _audit

_OWNER_INVITES = {
    MembershipRole.EDITOR,
    MembershipRole.AUTHOR,
    MembershipRole.CONTRIBUTOR,
}
_EDITOR_INVITES = {MembershipRole.AUTHOR, MembershipRole.CONTRIBUTOR}


def create_invitation(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    payload: InvitationCreate,
    email_service: EmailService,
) -> tuple[PublicationInvitation, EmailResult]:
    """Invite an email address. The invitation cannot grant ownership or a platform role."""

    publication = require_publication(session, publication_id, lock=True)
    require_active_publication(publication)
    membership = require_active_member(session, publication, actor)
    role = MembershipRole(payload.role)
    _require_invite_power(publication, membership, role)
    existing_user = UserRepository(session).get_by_email(payload.email)
    if existing_user is not None:
        current = membership_for(session, publication.id, existing_user.id)
        if current is not None and current.status is MembershipStatus.ACTIVE:
            raise ConflictError("This person is already a member.")
        if current is not None and current.status is MembershipStatus.SUSPENDED:
            raise ConflictError("That member is suspended.")
    invitations = InvitationRepository(session)
    now = datetime.now(UTC)
    invitations.expire_due(publication.id, now)
    if invitations.pending_for_email(publication.id, payload.email) is not None:
        raise ConflictError("An invitation is already pending for that email.")
    token = generate_opaque_token()
    expires_at = now + timedelta(hours=get_settings().invitation_expire_hours)
    invitation = PublicationInvitation(
        publication_id=publication.id,
        email=payload.email,
        email_key=payload.email,
        role=role,
        token_hash=hash_opaque_token(token),
        invited_by_id=actor.id,
        status=InvitationStatus.PENDING,
        expires_at=expires_at,
    )
    try:
        invitations.add(invitation)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("An invitation is already pending for that email.") from exc
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="member_invited",
        target_user_id=existing_user.id if existing_user is not None else None,
        new_value=role.value,
    )
    if existing_user is not None:
        from app.services.notification_events import invitation_received

        invitation_received(
            session,
            recipient_id=existing_user.id,
            actor=actor,
            publication=publication,
            invitation_id=invitation.id,
        )
    result = email_service.send_publication_invitation(
        recipient=payload.email,
        token=token,
        publication_name=publication.name,
        expires_at=expires_at,
    )
    invitation.invited_by = actor
    return invitation, result


def list_invitations(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    *,
    page: int,
    page_size: int,
) -> tuple[list[PublicationInvitation], int]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    require_editor(membership)
    InvitationRepository(session).expire_due(publication.id, datetime.now(UTC))
    return InvitationRepository(session).page(publication.id, page=page, page_size=page_size)


def revoke_invitation(
    session: Session,
    publication_id: uuid.UUID,
    invitation_id: uuid.UUID,
    actor: User,
) -> PublicationInvitation:
    publication = require_publication(session, publication_id, lock=True)
    membership = require_active_member(session, publication, actor)
    invitation = InvitationRepository(session).get(invitation_id, lock=True)
    if invitation is None or invitation.publication_id != publication.id:
        raise NotFoundError("Invitation not found.")
    _require_revoke_power(publication, membership, invitation)
    _expire_if_needed(invitation)
    if invitation.status is not InvitationStatus.PENDING:
        raise ConflictError("That invitation is no longer pending.")
    invitation.status = InvitationStatus.REVOKED
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="invitation_revoked",
        new_value=invitation.role.value,
    )
    session.flush()
    return invitation


def accept_invitation(
    session: Session, actor: User, token: str
) -> PublicationMembership:
    """Accept a single-use invitation when the account email matches and is verified."""

    invitation = InvitationRepository(session).get_by_hash(
        hash_opaque_token(token.strip()), lock=True
    )
    if invitation is None:
        raise NotFoundError("Invitation not found.")
    now = datetime.now(UTC)
    if invitation.status is InvitationStatus.PENDING and ensure_utc(invitation.expires_at) <= now:
        invitation.status = InvitationStatus.EXPIRED
        session.flush()
        raise ConflictError("This invitation has expired.")
    if invitation.status is InvitationStatus.EXPIRED:
        raise ConflictError("This invitation has expired.")
    if invitation.status is InvitationStatus.REVOKED:
        raise ConflictError("This invitation was revoked.")
    if invitation.status is InvitationStatus.ACCEPTED:
        raise ConflictError("This invitation has already been used.")
    if invitation.status is not InvitationStatus.PENDING:
        raise ConflictError("This invitation is no longer valid.")
    if not actor.is_verified:
        raise ServiceError("Email verification is required.", 403)
    if actor.email.casefold() != invitation.email_key:
        raise ServiceError(
            "This invitation was sent to a different email address.", 403
        )
    publication = require_publication(session, invitation.publication_id, lock=True)
    current = membership_for(session, publication.id, actor.id)
    if current is not None and current.status is MembershipStatus.ACTIVE:
        raise ConflictError("This person is already a member.")
    if current is not None and current.status is MembershipStatus.SUSPENDED:
        raise ConflictError("That member is suspended.")
    if current is None:
        current = MembershipRepository(session).add(
            PublicationMembership(
                publication_id=publication.id,
                user_id=actor.id,
                role=invitation.role,
                status=MembershipStatus.ACTIVE,
                joined_at=now,
            )
        )
    else:
        current.role = invitation.role
        current.status = MembershipStatus.ACTIVE
        current.joined_at = now
        current.updated_at = now
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = now
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="invitation_accepted",
        target_user_id=actor.id,
        new_value=invitation.role.value,
    )
    from app.services.notification_events import invitation_accepted

    invitation_accepted(
        session, actor=actor, publication=publication, invitation_id=invitation.id
    )
    session.flush()
    current.user = actor
    return current


def _require_invite_power(publication, membership, role: MembershipRole) -> None:
    if membership.role is MembershipRole.OWNER and role in _OWNER_INVITES:
        return
    if (
        membership.role is MembershipRole.EDITOR
        and publication.editors_can_invite
        and role in _EDITOR_INVITES
    ):
        return
    if membership.role is MembershipRole.EDITOR and role is MembershipRole.EDITOR:
        raise ServiceError("Editors cannot invite other editors.", 403)
    raise ServiceError(FORBIDDEN, 403)


def _require_revoke_power(publication, membership, invitation: PublicationInvitation) -> None:
    if membership.role is MembershipRole.OWNER:
        return
    if (
        membership.role is MembershipRole.EDITOR
        and publication.editors_can_invite
        and invitation.role in _EDITOR_INVITES
    ):
        return
    raise ServiceError(FORBIDDEN, 403)


def _expire_if_needed(invitation: PublicationInvitation) -> None:
    if (
        invitation.status is InvitationStatus.PENDING
        and ensure_utc(invitation.expires_at) <= datetime.now(UTC)
    ):
        invitation.status = InvitationStatus.EXPIRED
