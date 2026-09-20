from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.secrets.client import LocalSecretsClient
from theshed.settings.galileo import (
    apply_galileo_runtime,
    read_galileo_settings,
    write_galileo_settings,
)
from theshed.settings.service import (
    list_live_models,
    list_sub_agent_settings,
    resolved_runtime_choice,
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


class GalileoSettingsResponse(BaseModel):
    project: str
    host: str
    log_stream: str
    api_key_set: bool
    configured: bool


class GalileoSettingsRequest(BaseModel):
    project: str | None = None
    host: str | None = None
    log_stream: str | None = None
    api_key: str | None = None


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
    if llm is None:
        return ConnectionResponse(provider=None, model=None, configured=False)
    vendor = getattr(llm, "vendor", None)
    provider, model = await resolved_runtime_choice(db, vendor)
    return ConnectionResponse(provider=provider, model=model, configured=True)


@router.get("/galileo", dependencies=[Depends(get_current_user_id)])
async def get_galileo_settings(request: Request) -> GalileoSettingsResponse:
    settings = read_galileo_settings(getattr(request.app.state, "secrets", None))
    return GalileoSettingsResponse(
        project=settings.project,
        host=settings.host,
        log_stream=settings.log_stream,
        api_key_set=settings.api_key_set,
        configured=settings.configured,
    )


@router.post("/galileo", dependencies=[Depends(require_csrf)])
async def post_galileo_settings(
    body: GalileoSettingsRequest, request: Request
) -> GalileoSettingsResponse:
    secrets = getattr(request.app.state, "secrets", None)
    settings = write_galileo_settings(
        secrets,
        project=body.project,
        host=body.host,
        log_stream=body.log_stream,
        api_key=body.api_key,
    )
    apply_galileo_runtime(request.app.state, secrets)
    return GalileoSettingsResponse(
        project=settings.project,
        host=settings.host,
        log_stream=settings.log_stream,
        api_key_set=settings.api_key_set,
        configured=settings.configured,
    )


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
    llm = getattr(request.app.state, "llm_client", None)
    live_vendor = getattr(llm, "vendor", None) if llm is not None else None
    if body.provider and body.model:
        if live_vendor is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Save a provider key first, then assign a model for that provider.",
            )
        if body.provider != live_vendor:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Chat is using {live_vendor}. Save a {body.provider} key first, "
                "then assign that provider's model.",
            )
    await set_model_assignments(
        db=db,
        sub_agent_ids=body.sub_agent_ids,
        provider=body.provider,
        model=body.model,
        set_by_user_id=uuid.UUID(user_id),
    )
    _provider, resolved_model = await resolved_runtime_choice(db, live_vendor)
    if resolved_model:
        request.app.state.classifier_model = resolved_model
    settings = await list_sub_agent_settings(db)
    return [SubAgentSettingResponse(**vars(s)) for s in settings]
