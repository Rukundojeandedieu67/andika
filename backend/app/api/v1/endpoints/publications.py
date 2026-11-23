"""Public profiles and editorial management for publications."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import DatabaseSession, SettingsDep, VerifiedUser
from app.core.rate_limit import limit_invitations
from app.models.editorial import EditorialEvent
from app.models.post import Post
from app.schemas.common import ErrorResponse
from app.schemas.editorial import EditorialEventRead, EditorialPostDetail
from app.schemas.post import AuthorPublic, PostListParams, PostPage, PostRead
from app.schemas.publication import (
    InvitationCreate,
    InvitationCreated,
    InvitationPage,
    InvitationRead,
    MemberPage,
    MemberRead,
    MemberRoleUpdate,
    OwnershipTransfer,
    PublicationAuditPage,
    PublicationAuditRead,
    PublicationCreate,
    PublicationManage,
    PublicationMinePage,
    PublicationPage,
    PublicationPublic,
    PublicationUpdate,
)
from app.services import editorial_service, invitation_service, publication_service
from app.services.email_service import EmailService, EmailStatus, get_email_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
EmailDep = Annotated[EmailService, Depends(get_email_service)]


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _posts(items: list[Post], params: PostListParams, total: int) -> PostPage:
    return PostPage(
        items=[PostRead.model_validate(item) for item in items],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


def _detail(post: Post, events: list[EditorialEvent]) -> EditorialPostDetail:
    detail = EditorialPostDetail.model_validate(post)
    detail.events = [
        EditorialEventRead(
            id=event.id,
            action=event.action,
            from_status=event.from_status,
            to_status=event.to_status,
            reason=event.reason,
            created_at=event.created_at,
            actor=AuthorPublic.model_validate(event.actor),
        )
        for event in events
    ]
    return detail


@router.get("", response_model=PublicationPage, summary="List public publications")
def list_publications(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> PublicationPage:
    """Return active public publications. Private and inactive ones are omitted."""

    items, total = publication_service.list_public(
        session, page=page, page_size=page_size, search=search
    )
    return PublicationPage(
        items=[publication_service.to_public(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=PublicationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a publication",
    responses=_ERRORS,
)
def create_publication(
    payload: PublicationCreate, actor: VerifiedUser, session: DatabaseSession
) -> PublicationPublic:
    """Create a publication. The caller becomes its owner and stays in their platform role."""

    try:
        publication = publication_service.create_publication(session, actor, payload)
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_public(publication)


@router.get(
    "/mine",
    response_model=PublicationMinePage,
    summary="List my publications",
    responses=_ERRORS,
)
def list_my_publications(
    actor: VerifiedUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PublicationMinePage:
    """Return publications where the caller is an active member."""

    items, total = publication_service.list_mine(
        session, actor, page=page, page_size=page_size
    )
    return PublicationMinePage(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/{slug}",
    response_model=PublicationPublic,
    summary="Read a public publication",
    responses=_ERRORS,
)
def read_publication(slug: str, session: DatabaseSession) -> PublicationPublic:
    """Return one active public publication."""

    try:
        publication = publication_service.get_public_by_slug(session, slug)
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_public(publication)


@router.get(
    "/{slug}/posts",
    response_model=PostPage,
    summary="List a publication's articles",
    responses=_ERRORS,
)
def list_publication_posts(
    slug: str,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    tag: Annotated[str | None, Query(max_length=120)] = None,
) -> PostPage:
    """Return published articles for an active public publication."""

    params = PostListParams(
        page=page, page_size=page_size, search=search, category=category, tag=tag
    )
    try:
        items, total = publication_service.list_public_posts(session, slug, params)
    except ServiceError as exc:
        _raise(exc)
    return _posts(items, params, total)


@router.get(
    "/{publication_id}/manage",
    response_model=PublicationManage,
    summary="Read publication management details",
    responses=_ERRORS,
)
def read_management(
    publication_id: UUID, actor: VerifiedUser, session: DatabaseSession
) -> PublicationManage:
    """Return settings for an active member. Non-members receive not found."""

    try:
        return publication_service.get_manage(session, publication_id, actor)
    except ServiceError as exc:
        _raise(exc)


@router.patch(
    "/{publication_id}",
    response_model=PublicationPublic,
    summary="Update a publication",
    responses=_ERRORS,
)
def update_publication(
    publication_id: UUID,
    payload: PublicationUpdate,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> PublicationPublic:
    """Update the fields the caller's publication role allows."""

    try:
        publication = publication_service.update_publication(
            session, publication_id, actor, payload
        )
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_public(publication)


@router.post(
    "/{publication_id}/archive",
    response_model=PublicationManage,
    summary="Archive a publication",
    responses=_ERRORS,
)
def archive_publication(
    publication_id: UUID, actor: VerifiedUser, session: DatabaseSession
) -> PublicationManage:
    try:
        publication_service.archive_publication(session, publication_id, actor)
        return publication_service.get_manage(session, publication_id, actor)
    except ServiceError as exc:
        _raise(exc)


@router.post(
    "/{publication_id}/restore",
    response_model=PublicationManage,
    summary="Restore an archived publication",
    responses=_ERRORS,
)
def restore_publication(
    publication_id: UUID, actor: VerifiedUser, session: DatabaseSession
) -> PublicationManage:
    try:
        publication_service.restore_publication(session, publication_id, actor)
        return publication_service.get_manage(session, publication_id, actor)
    except ServiceError as exc:
        _raise(exc)


@router.get(
    "/{publication_id}/members",
    response_model=MemberPage,
    summary="List publication members",
    responses=_ERRORS,
)
def list_members(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MemberPage:
    try:
        items, total = publication_service.list_members(
            session, publication_id, actor, page=page, page_size=page_size
        )
    except ServiceError as exc:
        _raise(exc)
    return MemberPage(
        items=[publication_service.to_member(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch(
    "/{publication_id}/members/{member_id}",
    response_model=MemberRead,
    summary="Change a member role",
    responses=_ERRORS,
)
def change_member_role(
    publication_id: UUID,
    member_id: UUID,
    payload: MemberRoleUpdate,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> MemberRead:
    try:
        membership = publication_service.change_member_role(
            session, publication_id, member_id, actor, payload
        )
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_member(membership)


@router.post(
    "/{publication_id}/members/{member_id}/suspend",
    response_model=MemberRead,
    summary="Suspend a member",
    responses=_ERRORS,
)
def suspend_member(
    publication_id: UUID,
    member_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> MemberRead:
    try:
        membership = publication_service.suspend_member(
            session, publication_id, member_id, actor
        )
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_member(membership)


@router.post(
    "/{publication_id}/members/{member_id}/remove",
    response_model=MemberRead,
    summary="Remove a member",
    responses=_ERRORS,
)
def remove_member(
    publication_id: UUID,
    member_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> MemberRead:
    try:
        membership = publication_service.remove_member(
            session, publication_id, member_id, actor
        )
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_member(membership)


@router.post(
    "/{publication_id}/transfer-ownership",
    response_model=PublicationManage,
    summary="Transfer publication ownership",
    responses=_ERRORS,
)
def transfer_ownership(
    publication_id: UUID,
    payload: OwnershipTransfer,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> PublicationManage:
    try:
        publication_service.transfer_ownership(session, publication_id, actor, payload)
        return publication_service.get_manage(session, publication_id, actor)
    except ServiceError as exc:
        _raise(exc)


@router.post(
    "/{publication_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a publication member",
    responses=_ERRORS,
)
def create_invitation(
    publication_id: UUID,
    payload: InvitationCreate,
    actor: VerifiedUser,
    session: DatabaseSession,
    settings: SettingsDep,
    email_service: EmailDep,
) -> InvitationCreated:
    limit_invitations(settings, str(actor.id))
    try:
        invitation, result = invitation_service.create_invitation(
            session, publication_id, actor, payload, email_service
        )
    except ServiceError as exc:
        _raise(exc)
    delivery, message = _delivery_message(result.status)
    return InvitationCreated(
        invitation=InvitationRead.model_validate(invitation),
        email_delivery=delivery,
        message=message,
    )


@router.get(
    "/{publication_id}/invitations",
    response_model=InvitationPage,
    summary="List publication invitations",
    responses=_ERRORS,
)
def list_invitations(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InvitationPage:
    try:
        items, total = invitation_service.list_invitations(
            session, publication_id, actor, page=page, page_size=page_size
        )
    except ServiceError as exc:
        _raise(exc)
    return InvitationPage(
        items=[InvitationRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{publication_id}/invitations/{invitation_id}/revoke",
    response_model=InvitationRead,
    summary="Revoke an invitation",
    responses=_ERRORS,
)
def revoke_invitation(
    publication_id: UUID,
    invitation_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> InvitationRead:
    try:
        invitation = invitation_service.revoke_invitation(
            session, publication_id, invitation_id, actor
        )
    except ServiceError as exc:
        _raise(exc)
    return InvitationRead.model_validate(invitation)


@router.get(
    "/{publication_id}/editorial/posts",
    response_model=PostPage,
    summary="List publication drafts and articles",
    responses=_ERRORS,
)
def list_editorial_posts(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> PostPage:
    params = PostListParams(page=page, page_size=page_size, search=search)
    try:
        items, total = editorial_service.list_posts(session, publication_id, actor, params)
    except ServiceError as exc:
        _raise(exc)
    return _posts(items, params, total)


@router.get(
    "/{publication_id}/editorial/posts/{post_id}",
    response_model=EditorialPostDetail,
    summary="Read one publication article and its editorial history",
    responses=_ERRORS,
)
def read_editorial_post(
    publication_id: UUID,
    post_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
) -> EditorialPostDetail:
    try:
        post, events = editorial_service.get_post(session, publication_id, post_id, actor)
    except ServiceError as exc:
        _raise(exc)
    return _detail(post, events)


@router.get(
    "/{publication_id}/editorial/submissions",
    response_model=PostPage,
    summary="List articles waiting for editors",
    responses=_ERRORS,
)
def list_submissions(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PostPage:
    params = PostListParams(page=page, page_size=page_size)
    try:
        items, total = editorial_service.list_submissions(
            session, publication_id, actor, params
        )
    except ServiceError as exc:
        _raise(exc)
    return _posts(items, params, total)


@router.get(
    "/{publication_id}/audit-logs",
    response_model=PublicationAuditPage,
    summary="List publication audit history",
    responses=_ERRORS,
)
def list_audit_logs(
    publication_id: UUID,
    actor: VerifiedUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PublicationAuditPage:
    """Return append-only management history for an owner or editor."""

    try:
        items, total = publication_service.list_audit(
            session, publication_id, actor, page=page, page_size=page_size
        )
    except ServiceError as exc:
        _raise(exc)
    return PublicationAuditPage(
        items=[
            PublicationAuditRead(
                id=item.id,
                action=item.action,
                previous_value=item.previous_value,
                new_value=item.new_value,
                created_at=item.created_at,
                actor=AuthorPublic.model_validate(item.actor),
                target=None
                if item.target is None
                else AuthorPublic.model_validate(item.target),
            )
            for item in items
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def _delivery_message(delivery: EmailStatus) -> tuple[str, str]:
    if delivery is EmailStatus.SENT:
        return "sent", "An invitation email has been sent."
    if delivery is EmailStatus.NOT_CONFIGURED:
        return (
            "not_configured",
            "The invitation was created, but email delivery is not configured.",
        )
    return "failed", "The invitation was created, but the email could not be sent."
