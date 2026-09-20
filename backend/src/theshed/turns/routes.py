from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from theshed.agents.orchestrator import ToolExecutor
from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.models import PendingTurnApproval
from theshed.db.session import get_session
from theshed.settings.service import resolved_runtime_choice
from theshed.turns.service import resume_turn, stream_turn, verify_turn

router = APIRouter(prefix="/turns", tags=["turns"])


class SubmitTurnRequest(BaseModel):
    conversation_id: str | None = None
    message: str


class VerifyTurnResponse(BaseModel):
    result: str


class RespondToApprovalRequest(BaseModel):
    approved: bool


@router.post("", dependencies=[Depends(require_csrf)])
async def submit_turn(
    body: SubmitTurnRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> EventSourceResponse:
    conversation_id = uuid.UUID(body.conversation_id) if body.conversation_id else None
    generator = stream_turn(
        db=db,
        user_id=uuid.UUID(user_id),
        conversation_id=conversation_id,
        message=body.message,
        llm=request.app.state.llm_client,
        classifier_model=await _resolved_turn_model(request, db),
        tracer=request.app.state.tracer_factory(),
        tool_executor=_tool_executor(request, db),
    )
    return EventSourceResponse(generator)


@router.post("/{turn_id}/verify", dependencies=[Depends(require_csrf)])
async def verify(
    turn_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> VerifyTurnResponse:
    verification = await verify_turn(
        db=db,
        turn_id=uuid.UUID(turn_id),
        user_id=uuid.UUID(user_id),
        llm=request.app.state.llm_client,
        verifier_model=await _resolved_turn_model(request, db),
        tracer=request.app.state.tracer_factory(),
    )
    if verification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turn not found or not yet completed")
    return VerifyTurnResponse(result=verification.result)


@router.post("/{turn_id}/approvals", dependencies=[Depends(require_csrf)])
async def respond_to_approval(
    turn_id: str,
    body: RespondToApprovalRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),  # auth gate; approvals aren't attributed to a user
) -> EventSourceResponse:
    pending = await db.get(PendingTurnApproval, uuid.UUID(turn_id))
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending approval for this turn")
    generator = resume_turn(
        db=db,
        pending=pending,
        approved=body.approved,
        llm=request.app.state.llm_client,
        classifier_model=await _resolved_turn_model(request, db),
        tracer=request.app.state.tracer_factory(),
        tool_executor=_tool_executor(request, db),
    )
    return EventSourceResponse(generator)


async def _resolved_turn_model(request: Request, db: AsyncSession) -> str:
    """Classify, synthesize, and verify use the same live vendor+model as chat."""
    llm = getattr(request.app.state, "llm_client", None)
    vendor = getattr(llm, "vendor", None) if llm is not None else None
    _provider, model = await resolved_runtime_choice(db, vendor)
    if model:
        request.app.state.classifier_model = model
        return model
    return getattr(request.app.state, "classifier_model", "") or ""


def _tool_executor(request: Request, db: AsyncSession) -> ToolExecutor | None:
    factory = getattr(request.app.state, "tool_executor_factory", None)
    if callable(factory):
        executor = factory(db)
        return executor if callable(executor) else None
    executor = getattr(request.app.state, "tool_executor", None)
    return executor if callable(executor) else None
