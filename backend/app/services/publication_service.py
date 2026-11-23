"""Create and manage publications. Permissions are enforced here, not only in routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.media import Media
from app.models.post import Post
from app.models.publication import (
    MembershipRole,
    MembershipStatus,
    Publication,
    PublicationAuditLog,
    PublicationMembership,
    PublicationStatus,
    PublicationVisibility,
)
from app.models.user import User, UserRole
from app.repositories.post_repository import PostRepository
from app.repositories.publication_repository import (
    MembershipRepository,
    PublicationAuditRepository,
    PublicationRepository,
)
from app.schemas.post import AuthorPublic, PostListParams
from app.schemas.publication import (
    MemberRead,
    MemberRoleUpdate,
    OwnershipTransfer,
    PublicationCreate,
    PublicationManage,
    PublicationMineItem,
    PublicationPublic,
    PublicationUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, ServiceError
from app.services.publication_access import (
    FORBIDDEN,
    NOT_FOUND,
    require_active_member,
    require_active_publication,
    require_owner,
    require_publication,
)
from app.services.search_text import refresh_for_publication
from app.services.slug import slugify, with_suffix

_OWNER_FIELDS = {
    "name",
    "slug",
    "visibility",
    "requires_review",
    "editors_can_invite",
}
_EDITOR_FIELDS = {
    "description",
    "website_url",
    "contact_email",
    "logo_media_id",
    "cover_media_id",
}


def create_publication(session: Session, actor: User, payload: PublicationCreate) -> Publication:
    """Open a publication and make the caller its owner. Platform role is unchanged."""

    publications = PublicationRepository(session)
    slug = payload.slug or _allocate_slug(publications, payload.name)
    if publications.slug_in_use(slug):
        raise ConflictError("That slug is already in use.")
    publication = Publication(
        name=payload.name,
        slug=slug,
        description=payload.description,
        website_url=payload.website_url,
        contact_email=payload.contact_email,
        owner_id=actor.id,
        visibility=payload.visibility,
        status=PublicationStatus.ACTIVE,
        requires_review=payload.requires_review,
        editors_can_invite=payload.editors_can_invite,
        logo_media=_attach(session, payload.logo_media_id, actor),
        cover_media=_attach(session, payload.cover_media_id, actor),
    )
    try:
        publications.add(publication)
        MembershipRepository(session).add(
            PublicationMembership(
                publication_id=publication.id,
                user_id=actor.id,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
                joined_at=datetime.now(UTC),
            )
        )
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That slug is already in use.") from exc
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="publication_created",
        new_value=publication.slug,
    )
    return _reload(session, publication.id)


def list_public(
    session: Session, *, page: int, page_size: int, search: str | None
) -> tuple[list[Publication], int]:
    return PublicationRepository(session).page_public(
        page=page, page_size=page_size, search=search
    )


def list_public_posts(
    session: Session, slug: str, params: PostListParams
) -> tuple[list[Post], int]:
    publication = get_public_by_slug(session, slug)
    return PostRepository(session).list_for_publication(publication.id, params)


def get_public_by_slug(session: Session, slug: str) -> Publication:
    publication = PublicationRepository(session).get_by_slug(slug)
    if not _is_public(publication):
        raise NotFoundError(NOT_FOUND)
    return publication


def list_mine(
    session: Session, actor: User, *, page: int, page_size: int
) -> tuple[list[PublicationMineItem], int]:
    rows, total = PublicationRepository(session).page_for_member(
        actor.id, page=page, page_size=page_size
    )
    items = [
        PublicationMineItem(
            id=publication.id,
            name=publication.name,
            slug=publication.slug,
            visibility=publication.visibility,
            status=publication.status,
            role=membership.role,
            membership_status=membership.status,
        )
        for publication, membership in rows
    ]
    return items, total


def get_manage(session: Session, publication_id: uuid.UUID, actor: User) -> PublicationManage:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    loaded = _reload(session, publication.id)
    return to_manage(
        loaded,
        membership,
        MembershipRepository(session).count(publication.id),
    )


def update_publication(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    payload: PublicationUpdate,
) -> Publication:
    publication = require_publication(session, publication_id, lock=True)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _reload(session, publication.id)
    if set(changes) == {"status"} and actor.role is UserRole.ADMIN:
        _apply_platform_status(session, publication, actor, changes["status"])
        return _reload(session, publication.id)
    membership = require_active_member(session, publication, actor)
    if "status" in changes:
        if actor.role is not UserRole.ADMIN:
            raise ServiceError(
                "Only a platform administrator can suspend a publication.", 403
            )
        _apply_platform_status(session, publication, actor, changes.pop("status"))
    if not changes:
        publication.updated_at = datetime.now(UTC)
        return _reload(session, publication.id)
    allowed = _EDITOR_FIELDS if membership.role is MembershipRole.EDITOR else None
    if membership.role is MembershipRole.OWNER:
        allowed = _OWNER_FIELDS | _EDITOR_FIELDS
    if allowed is None:
        raise ServiceError(FORBIDDEN, 403)
    if set(changes) - allowed:
        raise ServiceError(FORBIDDEN, 403)
    _apply_settings(session, publication, actor, changes)
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="publication_updated",
        new_value=",".join(sorted(changes)),
    )
    return _reload(session, publication.id)


def archive_publication(
    session: Session, publication_id: uuid.UUID, actor: User
) -> Publication:
    publication = require_publication(session, publication_id, lock=True)
    membership = require_active_member(session, publication, actor)
    require_owner(membership)
    if publication.status is not PublicationStatus.ACTIVE:
        raise ConflictError("Only an active publication can be archived.")
    publication.status = PublicationStatus.ARCHIVED
    publication.updated_at = datetime.now(UTC)
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="publication_archived",
        previous_value=PublicationStatus.ACTIVE.value,
        new_value=PublicationStatus.ARCHIVED.value,
    )
    return _reload(session, publication.id)


def restore_publication(
    session: Session, publication_id: uuid.UUID, actor: User
) -> Publication:
    publication = require_publication(session, publication_id, lock=True)
    membership = require_active_member(session, publication, actor)
    require_owner(membership)
    if publication.status is not PublicationStatus.ARCHIVED:
        raise ConflictError("Only an archived publication can be restored.")
    publication.status = PublicationStatus.ACTIVE
    publication.updated_at = datetime.now(UTC)
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="publication_restored",
        previous_value=PublicationStatus.ARCHIVED.value,
        new_value=PublicationStatus.ACTIVE.value,
    )
    return _reload(session, publication.id)


def list_members(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    *,
    page: int,
    page_size: int,
) -> tuple[list[PublicationMembership], int]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    include_inactive = membership.role in {MembershipRole.OWNER, MembershipRole.EDITOR}
    return MembershipRepository(session).page(
        publication.id,
        page=page,
        page_size=page_size,
        include_inactive=include_inactive,
    )


def change_member_role(
    session: Session,
    publication_id: uuid.UUID,
    member_id: uuid.UUID,
    actor: User,
    payload: MemberRoleUpdate,
) -> PublicationMembership:
    publication = require_publication(session, publication_id, lock=True)
    actor_membership = require_active_member(session, publication, actor)
    require_owner(actor_membership)
    target = _member(session, publication.id, member_id)
    if target.role is MembershipRole.OWNER or target.user_id == publication.owner_id:
        raise ConflictError("Transfer ownership before changing the owner's role.")
    if target.status is not MembershipStatus.ACTIVE:
        raise ConflictError("Only an active member can change roles.")
    new_role = MembershipRole(payload.role)
    if target.role is new_role:
        raise ConflictError("That member already has this role.")
    previous = target.role.value
    target.role = new_role
    target.updated_at = datetime.now(UTC)
    log = _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="member_role_changed",
        target_user_id=target.user_id,
        previous_value=previous,
        new_value=new_role.value,
    )
    from app.models.notification import NotificationType
    from app.services.notification_events import membership_changed

    membership_changed(
        session,
        publication=publication,
        actor=actor,
        recipient_id=target.user_id,
        kind=NotificationType.PUBLICATION_MEMBER_ROLE_CHANGED,
        message=f"Your role at {publication.name} is now {new_role.value}.",
        audit_id=log.id,
    )
    session.flush()
    return target


def suspend_member(
    session: Session, publication_id: uuid.UUID, member_id: uuid.UUID, actor: User
) -> PublicationMembership:
    publication = require_publication(session, publication_id, lock=True)
    actor_membership = require_active_member(session, publication, actor)
    require_owner(actor_membership)
    target = _member(session, publication.id, member_id)
    if target.role is MembershipRole.OWNER or target.user_id == publication.owner_id:
        raise ConflictError("Transfer ownership before suspending the owner.")
    if target.status is not MembershipStatus.ACTIVE:
        raise ConflictError("Only an active member can be suspended.")
    target.status = MembershipStatus.SUSPENDED
    target.updated_at = datetime.now(UTC)
    log = _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="member_suspended",
        target_user_id=target.user_id,
        previous_value=MembershipStatus.ACTIVE.value,
        new_value=MembershipStatus.SUSPENDED.value,
    )
    from app.models.notification import NotificationType
    from app.services.notification_events import membership_changed

    membership_changed(
        session,
        publication=publication,
        actor=actor,
        recipient_id=target.user_id,
        kind=NotificationType.PUBLICATION_MEMBER_SUSPENDED,
        message=f"Your membership at {publication.name} was suspended.",
        audit_id=log.id,
    )
    session.flush()
    return target


def remove_member(
    session: Session, publication_id: uuid.UUID, member_id: uuid.UUID, actor: User
) -> PublicationMembership:
    publication = require_publication(session, publication_id, lock=True)
    actor_membership = require_active_member(session, publication, actor)
    require_owner(actor_membership)
    target = _member(session, publication.id, member_id)
    if target.role is MembershipRole.OWNER or target.user_id == publication.owner_id:
        raise ConflictError("Transfer ownership before removing the owner.")
    if target.status is MembershipStatus.REMOVED:
        raise ConflictError("That member is already removed.")
    previous = target.status.value
    target.status = MembershipStatus.REMOVED
    target.updated_at = datetime.now(UTC)
    log = _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="member_removed",
        target_user_id=target.user_id,
        previous_value=previous,
        new_value=MembershipStatus.REMOVED.value,
    )
    from app.models.notification import NotificationType
    from app.services.notification_events import membership_changed

    membership_changed(
        session,
        publication=publication,
        actor=actor,
        recipient_id=target.user_id,
        kind=NotificationType.PUBLICATION_MEMBER_REMOVED,
        message=f"You were removed from {publication.name}.",
        audit_id=log.id,
    )
    session.flush()
    return target


def transfer_ownership(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    payload: OwnershipTransfer,
) -> Publication:
    """Move ownership in one transaction and keep a single active owner."""

    publication = require_publication(session, publication_id, lock=True)
    current = require_active_member(session, publication, actor)
    require_owner(current)
    require_active_publication(publication)
    successor = MembershipRepository(session).for_user(publication.id, payload.user_id)
    if successor is None:
        raise NotFoundError("Member not found.")
    if successor.user_id == actor.id:
        raise ConflictError("You already own this publication.")
    if successor.status is not MembershipStatus.ACTIVE:
        raise ConflictError("Ownership can only move to an active member.")
    if successor.role is MembershipRole.OWNER:
        raise ConflictError("You already own this publication.")
    now = datetime.now(UTC)
    current.role = MembershipRole.EDITOR
    current.updated_at = now
    session.flush()
    successor.role = MembershipRole.OWNER
    successor.updated_at = now
    publication.owner_id = successor.user_id
    publication.updated_at = now
    log = _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action="ownership_transferred",
        target_user_id=successor.user_id,
        previous_value=str(actor.id),
        new_value=str(successor.user_id),
    )
    from app.models.notification import NotificationType
    from app.services.notification_events import membership_changed

    membership_changed(
        session,
        publication=publication,
        actor=actor,
        recipient_id=successor.user_id,
        kind=NotificationType.PUBLICATION_OWNERSHIP_TRANSFERRED,
        message=f"You are now the owner of {publication.name}.",
        audit_id=log.id,
    )
    session.flush()
    return _reload(session, publication.id)


def list_audit(
    session: Session,
    publication_id: uuid.UUID,
    actor: User,
    *,
    page: int,
    page_size: int,
) -> tuple[list[PublicationAuditLog], int]:
    publication = require_publication(session, publication_id)
    membership = require_active_member(session, publication, actor)
    if membership.role not in {MembershipRole.OWNER, MembershipRole.EDITOR}:
        raise ServiceError(FORBIDDEN, 403)
    return PublicationAuditRepository(session).page(
        publication.id, page=page, page_size=page_size
    )


def to_public(publication: Publication) -> PublicationPublic:
    return PublicationPublic(
        id=publication.id,
        name=publication.name,
        slug=publication.slug,
        description=publication.description,
        website_url=publication.website_url,
        contact_email=publication.contact_email,
        logo=_branding(publication.logo_media),
        cover=_branding(publication.cover_media),
        owner=AuthorPublic.model_validate(publication.owner),
        created_at=publication.created_at,
    )


def to_manage(
    publication: Publication, membership: PublicationMembership, member_count: int
) -> PublicationManage:
    return PublicationManage(
        **to_public(publication).model_dump(),
        visibility=publication.visibility,
        status=publication.status,
        requires_review=publication.requires_review,
        editors_can_invite=publication.editors_can_invite,
        caller_role=membership.role,
        member_count=member_count,
    )


def to_member(membership: PublicationMembership) -> MemberRead:
    return MemberRead(
        id=membership.id,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        user=AuthorPublic.model_validate(membership.user),
    )


def _apply_settings(
    session: Session, publication: Publication, actor: User, changes: dict[str, object]
) -> None:
    if "slug" in changes and changes["slug"] != publication.slug:
        slug = str(changes["slug"])
        if PublicationRepository(session).slug_in_use(slug, excluding=publication.id):
            raise ConflictError("That slug is already in use.")
        publication.slug = slug
    for field in (
        "name",
        "description",
        "website_url",
        "contact_email",
        "visibility",
        "requires_review",
        "editors_can_invite",
    ):
        if field in changes:
            setattr(publication, field, changes[field])
    if "logo_media_id" in changes:
        publication.logo_media = _attach(session, changes["logo_media_id"], actor)  # type: ignore[arg-type]
    if "cover_media_id" in changes:
        publication.cover_media = _attach(session, changes["cover_media_id"], actor)  # type: ignore[arg-type]
    publication.updated_at = datetime.now(UTC)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("That slug is already in use.") from exc
    if "name" in changes:
        refresh_for_publication(session, publication.id)


def _apply_platform_status(
    session: Session, publication: Publication, actor: User, status: str
) -> None:
    if actor.role is not UserRole.ADMIN:
        raise ServiceError("Only a platform administrator can suspend a publication.", 403)
    target = PublicationStatus(status)
    if target is PublicationStatus.SUSPENDED:
        if publication.status is not PublicationStatus.ACTIVE:
            raise ConflictError("Only an active publication can be suspended.")
        previous = publication.status.value
        publication.status = PublicationStatus.SUSPENDED
        action = "publication_suspended"
    else:
        if publication.status is not PublicationStatus.SUSPENDED:
            raise ConflictError("Only a suspended publication can be reinstated.")
        previous = publication.status.value
        publication.status = PublicationStatus.ACTIVE
        action = "publication_restored"
    publication.updated_at = datetime.now(UTC)
    _audit(
        session,
        publication_id=publication.id,
        actor_id=actor.id,
        action=action,
        previous_value=previous,
        new_value=publication.status.value,
    )


def _member(
    session: Session, publication_id: uuid.UUID, member_id: uuid.UUID
) -> PublicationMembership:
    membership = MembershipRepository(session).get(member_id)
    if membership is None or membership.publication_id != publication_id:
        raise NotFoundError("Member not found.")
    return membership


def _attach(session: Session, media_id: uuid.UUID | None, actor: User) -> Media | None:
    if media_id is None:
        return None
    from app.services.media_service import require_attachable

    return require_attachable(session, media_id, actor)


def _reload(session: Session, publication_id: uuid.UUID) -> Publication:
    publication = PublicationRepository(session).get_loaded(publication_id)
    if publication is None:
        raise NotFoundError(NOT_FOUND)
    return publication


def _is_public(publication: Publication | None) -> bool:
    return (
        publication is not None
        and publication.deleted_at is None
        and publication.status is PublicationStatus.ACTIVE
        and publication.visibility is PublicationVisibility.PUBLIC
    )


def _branding(media: Media | None) -> dict[str, object] | None:
    if media is None or media.deleted_at is not None:
        return None
    status = media.status.value if hasattr(media.status, "value") else str(media.status)
    if status != "ready":
        return None
    from app.services.media_service import variant_url

    try:
        url = variant_url(media, "medium")
    except ServiceError:
        url = None
    return {"media_id": media.id, "url": url}


def _allocate_slug(publications: PublicationRepository, name: str) -> str:
    base = slugify(name, fallback="publication")
    candidate = base
    number = 2
    while publications.slug_in_use(candidate):
        candidate = with_suffix(base, number)
        number += 1
        if number > 1000:
            raise ConflictError("A unique slug could not be created.")
    return candidate


def _audit(
    session: Session,
    *,
    publication_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    target_user_id: uuid.UUID | None = None,
    previous_value: str | None = None,
    new_value: str | None = None,
) -> PublicationAuditLog:
    return PublicationAuditRepository(session).add(
        PublicationAuditLog(
            publication_id=publication_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            action=action,
            previous_value=previous_value,
            new_value=new_value,
        )
    )
