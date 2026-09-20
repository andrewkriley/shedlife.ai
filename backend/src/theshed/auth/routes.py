from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.cookies import set_session_cookies
from theshed.auth.dependencies import CSRF_COOKIE, SESSION_COOKIE, get_redis
from theshed.auth.service import SessionStore, verify_password
from theshed.db.models import Identity
from theshed.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str
    username: str | None = None
    email: str | None = None

    def login_id(self) -> str:
        return (self.username or self.email or "").strip()


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
    redis_client: Redis = Depends(get_redis),
) -> dict[str, str]:
    login_id = body.login_id()
    result = await db.execute(
        select(Identity).where(Identity.provider == "local", Identity.provider_user_id == login_id)
    )
    identity = result.scalar_one_or_none()

    if identity is None or identity.password_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if not verify_password(body.password, identity.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    store = SessionStore(redis_client)
    session_id = await store.create(user_id=str(identity.user_id))
    set_session_cookies(response, session_id)
    return {"status": "ok"}


@router.post("/logout")
async def logout(
    response: Response,
    redis_client: Redis = Depends(get_redis),
    shed_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    if shed_session is not None:
        await SessionStore(redis_client).invalidate(shed_session)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"status": "ok"}
