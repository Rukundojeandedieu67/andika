"""Membership checks used by publication and article services."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.publication import (
    MembershipRole,
    MembershipStatus,
    Publication,
    PublicationMembership,
    PublicationStatus,
)
from app.models.user import User
from app.repositories.publication_repository import (
    MembershipRepository,
    PublicationRepository,
)
from app.services.exceptions import NotFoundError, ServiceError

NOT_FOUND = "Publication not found."
FORBIDDEN = "You do not have permission to manage this publication."
INACTIVE_MEMBER = "Your publication membership is not active."
INACTIVE_PUBLICATION = "This publication is not active."

EDITOR_ROLES = {MembershipRole.OWNER, MembershipRole.EDITOR}
STAFF_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.EDITOR,
    MembershipRole.AUTHOR,
    MembershipRole.CONTRIBUTOR,
}


def require_publication(
    session: Session, publication_id: uuid.UUID, *, lock: bool = False
) -> Publication:
    publication = PublicationRepository(session).get(publication_id, lock=lock)
    if publication is None or publication.deleted_at is not None:
        raise NotFoundError(NOT_FOUND)
    return publication


def membership_for(
    session: Session, publication_id: uuid.UUID, user_id: uuid.UUID
) -> PublicationMembership | None:
    return MembershipRepository(session).for_user(publication_id, user_id)


def require_active_member(
    session: Session, publication: Publication, user: User
) -> PublicationMembership:
    """Return the caller's active membership, or hide the publication."""

    membership = membership_for(session, publication.id, user.id)
    if membership is None:
        raise NotFoundError(NOT_FOUND)
    if membership.status is not MembershipStatus.ACTIVE:
        raise ServiceError(INACTIVE_MEMBER, 403)
    return membership


def require_owner(membership: PublicationMembership) -> None:
    if membership.role is not MembershipRole.OWNER:
        raise ServiceError(FORBIDDEN, 403)


def require_editor(membership: PublicationMembership) -> None:
    if membership.role not in EDITOR_ROLES:
        raise ServiceError(FORBIDDEN, 403)


def require_active_publication(publication: Publication) -> None:
    if publication.status is not PublicationStatus.ACTIVE:
        raise ServiceError(INACTIVE_PUBLICATION, 409)
