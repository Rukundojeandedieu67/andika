"""Token responses for API clients.

Browser applications should use the HttpOnly `andika_refresh_token` cookie and
keep the access token in memory. Do not persist the refresh token in
localStorage, sessionStorage, or a URL query parameter.
"""

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class MessageResponse(BaseModel):
    message: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str = Field(
        description=(
            "Returned for non-browser API clients. Browser clients must use the "
            "HttpOnly cookie and must not store this value in localStorage."
        )
    )
    user: UserPublic
