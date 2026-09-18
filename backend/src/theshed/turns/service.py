"""Turn lifecycle, per docs/spec/core-agentic-loop.md's Sequence."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.orchestrator import resolve_matches, run_sub_agent
from theshed.agents.providers.anthropic import LLMClient
from theshed.agents.registry import list_sub_agents
from theshed.agents.synthesis import synthesize
from theshed.agents.tool_loop import ApprovalRequired
from theshed.db.models import Conversation, Turn, TurnSubAgentResult
from theshed.observability.galileo import TurnTracer

RECENCY_CAP = 10  # tunable default, per docs/spec/core-agentic-loop.md
TOKEN_CHUNK_SIZE = 40


def _sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _load_context(db: AsyncSession, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
    """Only past turns' (user_message, final_response) pairs — not
    TurnSubAgentResult detail, which stays in that turn's own trace, not
    future context. See docs/spec/core-agentic-loop.md, Data section."""
    result = await db.execute(
        select(Turn)
        .where(Turn.conversation_id == conversation_id)
        .order_by(Turn.created_at.desc())
        .limit(RECENCY_CAP)
    )
    recent_turns = list(reversed(result.scalars().all()))
    messages: list[dict[str, Any]] = []
    for turn in recent_turns:
        messages.append({"role": "user", "content": turn.user_message})
        if turn.final_response:
            messages.append({"role": "assistant", "content": turn.final_response})
    return messages


def _chunk_text(text: str, size: int = TOKEN_CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


async def stream_turn(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    message: str,
    llm: LLMClient,
    classifier_model: str,
    tracer: TurnTracer,
) -> AsyncIterator[str]:
    is_new_conversation = conversation_id is None
    if is_new_conversation:
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        await db.flush()
        conversation_id = conversation.id
    assert conversation_id is not None  # true by construction: either passed in, or just set above

    context = await _load_context(db, conversation_id)

    turn = Turn(conversation_id=conversation_id, user_message=message)
    db.add(turn)
    await db.flush()

    if is_new_conversation:
        tracer.start_session(str(conversation_id))
    tracer.start_trace(message, str(turn.id))

    sub_agents = await list_sub_agents(db)

    tracer.start_span("classify", "classify", message)
    matches = await resolve_matches(message, sub_agents, llm, classifier_model)
    tracer.conclude_span(json.dumps([m.id for m in matches]))
    yield _sse("progress", {"stage": "classify:done"})

    results: dict[str, str] = {}
    worst_status = 0
    for sub_agent in matches:
        yield _sse("progress", {"stage": f"agent:{sub_agent.id} started"})
        tracer.start_span("agent", sub_agent.id, message)
        try:
            outcome = await run_sub_agent(sub_agent, message, context, llm)
        except ApprovalRequired as exc:
            yield _sse(
                "approval_required",
                {
                    "tool_name": exc.call.tool_name,
                    "arguments": exc.call.arguments,
                    "sub_agent_id": sub_agent.id,
                },
            )
            await db.commit()
            return

        tracer.conclude_span(outcome.result, outcome.status_code)
        results[sub_agent.id] = outcome.result
        worst_status = max(worst_status, outcome.status_code)
        db.add(
            TurnSubAgentResult(
                turn_id=turn.id,
                sub_agent_id=sub_agent.id,
                result=outcome.result,
                status_code=outcome.status_code,
            )
        )
        yield _sse("progress", {"stage": f"agent:{sub_agent.id} done", "status": outcome.status_code})

    if not results:
        final_response = "I wasn't able to find anything that could help with that."
        worst_status = 1
    elif len(results) == 1:
        final_response = next(iter(results.values()))
    else:
        yield _sse("progress", {"stage": "synthesis started"})
        final_response = synthesize(message, results, llm, classifier_model)

    for chunk in _chunk_text(final_response):
        yield _sse("token", {"text": chunk})

    turn.final_response = final_response
    tracer.conclude_trace(final_response, worst_status)
    await db.commit()

    yield _sse("done", {"turn_id": str(turn.id), "conversation_id": str(conversation_id)})
