from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.cookies import set_session_cookies
from theshed.auth.dependencies import get_redis
from theshed.auth.service import SessionStore, hash_password
from theshed.db.models import Identity, User
from theshed.db.session import get_session
from theshed.secrets.client import LocalSecretsClient
from theshed.setup.providers import ProviderRejected, validate_api_key

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupRequest(BaseModel):
    email: str
    password: str
    provider: str
    api_key: str
    galileo_api_key: str | None = None
    galileo_console_url: str | None = None


async def _identity_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Identity))
    return int(result.scalar_one())


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    return {"needed": await _identity_count(db) == 0}


@router.post("")
async def post_setup(
    body: SetupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
    redis_client: Redis = Depends(get_redis),
) -> dict[str, str]:
    if await _identity_count(db) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup already completed")

    live_check = getattr(request.app.state, "provider_live_check", None)
    try:
        validate_api_key(body.provider, body.api_key, live_check=live_check)
    except ProviderRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    user = User(display_name=body.email)
    db.add(user)
    await db.flush()
    db.add(
        Identity(
            user_id=user.id,
            provider="local",
            provider_user_id=body.email,
            password_hash=hash_password(body.password),
        )
    )
    await db.flush()

    secrets = request.app.state.secrets
    if isinstance(secrets, LocalSecretsClient):
        secrets.set("local://providers/llm/vendor", body.provider)
        secrets.set("local://providers/llm/api_key", body.api_key)
        if body.galileo_api_key:
            secrets.set("local://observability/galileo_api_key", body.galileo_api_key)
        if body.galileo_console_url:
            secrets.set("local://observability/galileo_console_url", body.galileo_console_url)

    configure = getattr(request.app.state, "configure_llm", None)
    if configure is not None:
        configure(body.provider, body.api_key)

    session_id = await SessionStore(redis_client).create(user_id=str(user.id))
    set_session_cookies(response, session_id)
    await db.commit()
    return {"status": "ok"}
