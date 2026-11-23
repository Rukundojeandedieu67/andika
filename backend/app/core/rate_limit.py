"""In-memory rate limits for sensitive authentication routes."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]

_LIMITERS: list[RateLimiter] = []


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds an authentication rate limit."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Too many requests. Try again later.")


class RateLimiter:
    """A fixed-window counter keyed by an arbitrary string."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        _LIMITERS.append(self)

    def check(self, key: str, *, limit: int | None = None) -> None:
        effective_limit = self.limit if limit is None else limit
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= effective_limit:
                retry_after = max(1, int(self.window_seconds - (now - hits[0])))
                raise RateLimitExceeded(retry_after)
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def reset_rate_limiters() -> None:
    """Clear counters. Tests use this so limits do not leak between cases."""

    for limiter in _LIMITERS:
        limiter.reset()


_login = RateLimiter(limit=10, window_seconds=15 * 60)
_register = RateLimiter(limit=5, window_seconds=60 * 60)
_refresh = RateLimiter(limit=30, window_seconds=15 * 60)
_forgot_password = RateLimiter(limit=5, window_seconds=60 * 60)
_reset_password = RateLimiter(limit=10, window_seconds=60 * 60)
_verify_email = RateLimiter(limit=10, window_seconds=60 * 60)
_resend_verification = RateLimiter(limit=3, window_seconds=60 * 60)
_media_upload = RateLimiter(limit=20, window_seconds=60 * 60)
_comments = RateLimiter(limit=300, window_seconds=60 * 60)
_reports = RateLimiter(limit=100, window_seconds=60 * 60)


def _client_key(request: Request, scope: str) -> str:
    host = request.client.host if request.client is not None else "unknown"
    return f"{scope}:{host}"


def _enforce(
    request: Request, settings: Settings, limiter: RateLimiter, scope: str
) -> None:
    if not settings.auth_rate_limit_enabled:
        return
    try:
        limiter.check(_client_key(request, scope))
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


def limit_login(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _login, "login")


def limit_register(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _register, "register")


def limit_refresh(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _refresh, "refresh")


def limit_forgot_password(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _forgot_password, "forgot-password")


def limit_reset_password(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _reset_password, "reset-password")


def limit_verify_email(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _verify_email, "verify-email")


def limit_resend_verification(request: Request, settings: SettingsDep) -> None:
    _enforce(request, settings, _resend_verification, "resend-verification")


def limit_media_upload(settings: Settings, user_id: str) -> None:
    """Limit image uploads per account. Disabled in tests with the auth limiter."""

    if not settings.auth_rate_limit_enabled:
        return
    try:
        _media_upload.check(f"media-upload:{user_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


def limit_comments(settings: Settings, user_id: str) -> None:
    """Limit new comments and replies for one account."""

    _limited(
        settings,
        _comments,
        f"comments:{user_id}",
        limit=settings.comment_rate_limit_per_hour,
    )


def limit_reports(settings: Settings, user_id: str) -> None:
    """Limit comment reports for one account."""

    _limited(
        settings,
        _reports,
        f"reports:{user_id}",
        limit=settings.report_rate_limit_per_hour,
    )


def _limited(settings: Settings, limiter: RateLimiter, key: str, *, limit: int) -> None:
    if not settings.auth_rate_limit_enabled:
        return
    try:
        limiter.check(key, limit=limit)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
