from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.models import resolve_runtime_model
from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.secrets.client import LocalSecretsClient
from theshed.settings.service import (
    list_live_models,
    list_sub_agent_settings,
    pick_connection_setting,
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


class ConnectionResponse(BaseModel):
    provider: str | None
    model: str | None
    configured: bool


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


@router.get("/connection", dependencies=[Depends(get_current_user_id)])
async def get_connection(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    llm = getattr(request.app.state, "llm_client", None)
    vendor = getattr(llm, "vendor", None) if llm is not None else None
    settings = await list_sub_agent_settings(db)
    if llm is None:
        return ConnectionResponse(provider=None, model=None, configured=False)
    chosen = pick_connection_setting(settings)
    if chosen is None:
        return ConnectionResponse(provider=vendor, model=None, configured=True)
    provider, model = resolve_runtime_model(
        client_vendor=vendor,
        default_provider=chosen.default_provider,
        default_model=chosen.default_model,
        override_provider=chosen.provider if chosen.overridden else None,
        override_model=chosen.model if chosen.overridden else None,
    )
    return ConnectionResponse(provider=provider, model=model, configured=True)


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
    request: Request,
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
    if body.model and (
        "bootstrap.intake" in body.sub_agent_ids or len(body.sub_agent_ids) == 1
    ):
        request.app.state.classifier_model = body.model
    settings = await list_sub_agent_settings(db)
    return [SubAgentSettingResponse(**vars(s)) for s in settings]
