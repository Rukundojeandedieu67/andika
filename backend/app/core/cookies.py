"""HttpOnly refresh-token cookie helpers.

Browser clients should keep the refresh token in this cookie and the access
token in memory. Do not store the refresh token in localStorage or in a query
string. The cookie path is limited to the authentication routes, HttpOnly
prevents JavaScript from reading it, and SameSite=Strict blocks cross-site
submission. The Secure flag is enabled in production.
"""

from fastapi import Response

from app.core.config import Settings

REFRESH_COOKIE_NAME = "andika_refresh_token"


def refresh_cookie_path(settings: Settings) -> str:
    return f"{settings.api_v1_prefix}/auth"


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path=refresh_cookie_path(settings),
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=refresh_cookie_path(settings),
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
    )
