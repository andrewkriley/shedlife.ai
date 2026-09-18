from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.settings.service import (
    list_live_models,
    list_sub_agent_settings,
    set_model_assignments,
)

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


@router.get("/sub-agents", dependencies=[Depends(get_current_user_id)])
async def get_sub_agent_settings(
    db: AsyncSession = Depends(get_session),
) -> list[SubAgentSettingResponse]:
    settings = await list_sub_agent_settings(db)
    return [SubAgentSettingResponse(**vars(s)) for s in settings]


@router.get("/models", dependencies=[Depends(get_current_user_id)])
async def get_live_models(request: Request) -> dict[str, list[str]]:
    clients = {"anthropic": request.app.state.llm_client}
    if request.app.state.openai_client is not None:
        clients["openai"] = request.app.state.openai_client
    return list_live_models(clients)


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
