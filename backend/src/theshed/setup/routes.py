from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.cookies import set_session_cookies
from theshed.auth.dependencies import get_redis
from theshed.auth.service import SessionStore, hash_password
from theshed.db.models import Identity, User
from theshed.db.session import get_session

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None

    def login_id(self) -> str:
        return (self.username or self.email or "").strip()


async def _identity_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Identity))
    return int(result.scalar_one())


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    identities = await _identity_count(db)
    return {"needed": identities == 0, "has_operator": identities > 0}


@router.post("")
async def post_setup(
    body: SetupRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
    redis_client: Redis = Depends(get_redis),
) -> dict[str, str]:
    identities = await _identity_count(db)
    if identities > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup already completed")

    login_id = body.login_id()
    if not login_id or not body.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username and password are required")
    user = User(display_name=login_id)
    db.add(user)
    await db.flush()
    db.add(
        Identity(
            user_id=user.id,
            provider="local",
            provider_user_id=login_id,
            password_hash=hash_password(body.password),
        )
    )
    await db.flush()
    user_id = str(user.id)

    session_id = await SessionStore(redis_client).create(user_id=user_id)
    set_session_cookies(response, session_id)
    await db.commit()
    return {"status": "ok"}
