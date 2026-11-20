"""Authentication and account-recovery endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.core.dependencies import CurrentUser, DatabaseSession
from app.core.rate_limit import (
    limit_forgot_password,
    limit_login,
    limit_refresh,
    limit_register,
    limit_resend_verification,
    limit_reset_password,
    limit_verify_email,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.schemas.common import ErrorResponse
from app.schemas.token import AccessTokenResponse, MessageResponse
from app.schemas.user import UserPublic
from app.services import auth_service
from app.services.email_service import EmailService, get_email_service
from app.services.exceptions import ServiceError

router = APIRouter()

_RATE_LIMIT_RESPONSE = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "model": ErrorResponse,
        "description": "Too many requests from this client. Retry after the indicated delay.",
        "headers": {
            "Retry-After": {
                "description": "Seconds to wait before trying again.",
                "schema": {"type": "string"},
            }
        },
    }
}

_DELIVERY_SENT = "If an account exists for that address, a message has been sent."
_DELIVERY_UNAVAILABLE = (
    "If an account exists for that address, the request was accepted, "
    "but email delivery is not configured."
)


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    if user_agent is not None:
        user_agent = user_agent[:255]
    ip_address = request.client.host if request.client is not None else None
    return user_agent, ip_address


def _presented_refresh_token(request: Request, body_token: str | None) -> str | None:
    if body_token and body_token.strip():
        return body_token.strip()
    cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if cookie and cookie.strip():
        return cookie.strip()
    return None


def _token_response(
    issued: auth_service.IssuedTokens, response: Response
) -> AccessTokenResponse:
    settings = get_settings()
    set_refresh_cookie(response, issued.refresh_token, settings)
    return AccessTokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        refresh_token=issued.refresh_token,
        user=UserPublic.model_validate(issued.user),
    )


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a reader account",
    dependencies=[Depends(limit_register)],
    responses=_RATE_LIMIT_RESPONSE,
)
def register(
    payload: RegisterRequest,
    session: DatabaseSession,
    mail: Annotated[EmailService, Depends(get_email_service)],
) -> UserPublic:
    """Create a reader. Administrator and author roles cannot be chosen here."""

    try:
        user = auth_service.register_user(session, payload, mail)
    except ServiceError as exc:
        _raise_service_error(exc)
    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    summary="Log in",
    dependencies=[Depends(limit_login)],
    responses=_RATE_LIMIT_RESPONSE,
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> AccessTokenResponse:
    """Authenticate with email and password and start a refresh session."""

    user_agent, ip_address = _client_context(request)
    try:
        issued = auth_service.authenticate_user(
            session,
            email=str(payload.email),
            password=payload.password,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return _token_response(issued, response)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Rotate a refresh token",
    dependencies=[Depends(limit_refresh)],
    responses=_RATE_LIMIT_RESPONSE,
)
def refresh(
    request: Request,
    response: Response,
    session: DatabaseSession,
    payload: RefreshRequest | None = None,
) -> AccessTokenResponse:
    """Issue a new access token and replace the presented refresh token."""

    raw_token = _presented_refresh_token(
        request,
        payload.refresh_token if payload is not None else None,
    )
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is invalid.",
        )
    user_agent, ip_address = _client_context(request)
    try:
        issued = auth_service.refresh_session(
            session,
            refresh_token=raw_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    return _token_response(issued, response)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
)
def logout(
    request: Request,
    response: Response,
    session: DatabaseSession,
    user: CurrentUser,
    payload: LogoutRequest | None = None,
) -> None:
    """Revoke the caller's refresh session and clear the refresh cookie."""

    raw_token = _presented_refresh_token(
        request,
        payload.refresh_token if payload is not None else None,
    )
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required.",
        )
    try:
        auth_service.logout_session(session, user_id=user.id, refresh_token=raw_token)
    except ServiceError as exc:
        _raise_service_error(exc)
    clear_refresh_cookie(response, get_settings())


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset",
    dependencies=[Depends(limit_forgot_password)],
    responses=_RATE_LIMIT_RESPONSE,
)
def forgot_password(
    payload: ForgotPasswordRequest,
    session: DatabaseSession,
    mail: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    """Accept a reset request without revealing whether the account exists."""

    try:
        auth_service.request_password_reset(
            session, email=str(payload.email), mail=mail
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    message = _DELIVERY_SENT if mail.can_deliver else _DELIVERY_UNAVAILABLE
    return MessageResponse(message=message)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset a password",
    dependencies=[Depends(limit_reset_password)],
    responses=_RATE_LIMIT_RESPONSE,
)
def reset_password(
    payload: ResetPasswordRequest,
    session: DatabaseSession,
    mail: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    """Set a new password when the reset token is valid, then revoke refresh sessions."""

    try:
        auth_service.reset_password(
            session,
            token=payload.token,
            password=payload.password,
            mail=mail,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ServiceError as exc:
        _raise_service_error(exc)
    return MessageResponse(message="Your password has been updated.")


@router.post(
    "/verify-email",
    response_model=UserPublic,
    summary="Verify an email address",
    dependencies=[Depends(limit_verify_email)],
    responses=_RATE_LIMIT_RESPONSE,
)
def verify_email(payload: VerifyEmailRequest, session: DatabaseSession) -> UserPublic:
    """Mark an account verified. The token is supplied in the JSON body."""

    try:
        user = auth_service.verify_email(session, token=payload.token)
    except ServiceError as exc:
        _raise_service_error(exc)
    return UserPublic.model_validate(user)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend email verification",
    dependencies=[Depends(limit_resend_verification)],
    responses=_RATE_LIMIT_RESPONSE,
)
def resend_verification(
    payload: ResendVerificationRequest,
    session: DatabaseSession,
    mail: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    """Request another verification message without revealing whether the account exists."""

    try:
        auth_service.resend_verification(session, email=str(payload.email), mail=mail)
    except ServiceError as exc:
        _raise_service_error(exc)
    message = _DELIVERY_SENT if mail.can_deliver else _DELIVERY_UNAVAILABLE
    return MessageResponse(message=message)
