"""FastAPI dependencies enforcing the session-cookie + CSRF contract from
docs/spec/auth.md: HttpOnly session cookie, double-submit CSRF cookie/header
pair required on state-changing requests.
"""

from __future__ import annotations

import secrets

from fastapi import Cookie, Header, HTTPException, Request, status
from redis.asyncio import Redis

from theshed.auth.service import SessionStore

SESSION_COOKIE = "shed_session"
CSRF_COOKIE = "shed_csrf"
CSRF_HEADER = "x-csrf-token"


def get_redis(request: Request) -> Redis:
    redis_client: Redis = request.app.state.redis
    return redis_client


async def get_current_user_id(
    request: Request,
    shed_session: str | None = Cookie(default=None),
) -> str:
    if shed_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    store = SessionStore(get_redis(request))
    user_id = await store.get_user_id(shed_session)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")
    return user_id


async def require_csrf(
    shed_csrf: str | None = Cookie(default=None),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
) -> None:
    """Applied to state-changing routes only. GET requests never mutate
    state, so they don't need it."""
    if not shed_csrf or not x_csrf_token or not secrets.compare_digest(shed_csrf, x_csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
