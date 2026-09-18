from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.turns.service import stream_turn, verify_turn

router = APIRouter(prefix="/turns", tags=["turns"])


class SubmitTurnRequest(BaseModel):
    conversation_id: str | None = None
    message: str


class VerifyTurnResponse(BaseModel):
    result: str


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
        classifier_model=request.app.state.classifier_model,
        tracer=request.app.state.tracer_factory(),
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
        verifier_model=request.app.state.classifier_model,
        tracer=request.app.state.tracer_factory(),
    )
    if verification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turn not found or not yet completed")
    return VerifyTurnResponse(result=verification.result)
