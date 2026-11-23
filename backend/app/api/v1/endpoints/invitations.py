"""Accept a publication invitation. The raw token is not stored."""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, DatabaseSession, SettingsDep
from app.core.rate_limit import limit_invitation_accepts
from app.schemas.common import ErrorResponse
from app.schemas.publication import InvitationAccept, MemberRead
from app.services import invitation_service, publication_service
from app.services.exceptions import ServiceError

router = APIRouter()

_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
}


def _raise(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/accept",
    response_model=MemberRead,
    summary="Accept a publication invitation",
    responses=_ERRORS,
)
def accept_invitation(
    payload: InvitationAccept,
    actor: CurrentUser,
    session: DatabaseSession,
    settings: SettingsDep,
) -> MemberRead:
    """Accept an invitation when the token, email, and verified account all match."""

    limit_invitation_accepts(settings, str(actor.id))
    try:
        membership = invitation_service.accept_invitation(session, actor, payload.token)
    except ServiceError as exc:
        _raise(exc)
    return publication_service.to_member(membership)
