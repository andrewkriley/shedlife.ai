from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.secrets.client import LocalSecretsClient
from theshed.settings.service import (
    list_live_models,
    list_sub_agent_settings,
    set_model_assignments,
)
from theshed.setup.providers import ProviderRejected, validate_api_key

router = APIRouter(prefix="/settings", tags=["settings"])


class SubAgentSettingResponse(BaseModel):
    id: str
    macro_category: str
    description: str
    default_provider: str
    default_model: str
    provider: str
    model: str
    overridden: bool


class ModelAssignmentRequest(BaseModel):
    sub_agent_ids: list[str]
    provider: str | None = None
    model: str | None = None


class ProviderKeyRequest(BaseModel):
    provider: str
    api_key: str


def listing_clients(app_state: Any) -> dict[str, Any]:
    clients: dict[str, Any] = {}
    llm = getattr(app_state, "llm_client", None)
    if llm is not None:
        clients[getattr(llm, "vendor", "anthropic")] = llm
    openai_client = getattr(app_state, "openai_client", None)
    if openai_client is not None:
        clients["openai"] = openai_client
    gemini_client = getattr(app_state, "gemini_client", None)
    if gemini_client is not None:
        clients["gemini"] = gemini_client
    return clients


@router.get("/sub-agents", dependencies=[Depends(get_current_user_id)])
async def get_sub_agent_settings(
    db: AsyncSession = Depends(get_session),
) -> list[SubAgentSettingResponse]:
    settings = await list_sub_agent_settings(db)
    return [SubAgentSettingResponse(**vars(s)) for s in settings]


@router.get("/models", dependencies=[Depends(get_current_user_id)])
async def get_live_models(request: Request) -> dict[str, list[str]]:
    return list_live_models(listing_clients(request.app.state))


@router.post("/provider", dependencies=[Depends(require_csrf)])
async def post_provider_key(body: ProviderKeyRequest, request: Request) -> dict[str, str]:
    live_check = getattr(request.app.state, "provider_live_check", None)
    try:
        validate_api_key(body.provider, body.api_key, live_check=live_check)
    except ProviderRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    secrets = getattr(request.app.state, "secrets", None)
    if isinstance(secrets, LocalSecretsClient):
        secrets.set("local://providers/llm/vendor", body.provider)
        secrets.set("local://providers/llm/api_key", body.api_key)
    configure = getattr(request.app.state, "configure_llm", None)
    if configure is not None:
        configure(body.provider, body.api_key)
    return {"status": "ok", "provider": body.provider}


@router.post("/model-assignments", dependencies=[Depends(require_csrf)])
async def post_model_assignments(
    body: ModelAssignmentRequest,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> list[SubAgentSettingResponse]:
    await set_model_assignments(
        db=db,
        sub_agent_ids=body.sub_agent_ids,
        provider=body.provider,
        model=body.model,
        set_by_user_id=uuid.UUID(user_id),
    )
    settings = await list_sub_agent_settings(db)
    return [SubAgentSettingResponse(**vars(s)) for s in settings]
