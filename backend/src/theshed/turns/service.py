"""Turn lifecycle, per docs/spec/core-agentic-loop.md's Sequence."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from galileo_core.schemas.logging.agent import AgentType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.orchestrator import (
    SubAgentPaused,
    ToolExecutor,
    resolve_matches,
    resume_sub_agent,
    run_sub_agent,
)
from theshed.agents.providers.anthropic import LLMClient
from theshed.agents.registry import get_sub_agent, list_sub_agents
from theshed.agents.synthesis import synthesize
from theshed.agents.verifier import verify
from theshed.db.models import (
    Conversation,
    PendingTurnApproval,
    SubAgent,
    Turn,
    TurnSubAgentResult,
    TurnVerification,
)
from theshed.observability.galileo import TurnTracer

RECENCY_CAP = 10  # tunable default, per docs/spec/core-agentic-loop.md
TOKEN_CHUNK_SIZE = 40


def _sse(event_type: str, data: dict[str, Any]) -> dict[str, str]:
    """`sse-starlette`'s `EventSourceResponse` does its own wire-formatting
    from a dict — it must not be handed an already-formatted SSE string, or
    the result is double-wrapped (each of our own lines gets a second
    `data: ` prefix). Caught by the live end-to-end verification, not by any
    mocked unit test — this class of bug is exactly why that step exists."""
    return {"event": event_type, "data": json.dumps(data)}


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


@dataclass
class _FanOutState:
    """Accumulates across one turn's sequential sub-agent fan-out — shared
    between a fresh run (`stream_turn`) and a resume after approval
    (`resume_turn`), since a resume picks up mid-fan-out with some results
    already in hand (see `PendingTurnApproval.completed_results`)."""

    results: dict[str, str] = field(default_factory=dict)
    status_codes: dict[str, int] = field(default_factory=dict)
    worst_status: int = 0
    paused: SubAgentPaused | None = None


async def _run_matches(
    db: AsyncSession,
    turn: Turn,
    message: str,
    context: list[dict[str, Any]],
    matches: list[SubAgent],
    llm: LLMClient,
    tracer: TurnTracer,
    state: _FanOutState,
    tool_executor: ToolExecutor | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Runs each of `matches` in turn, per spec step 6. If one pauses for
    approval, persists everything needed to resume later (this sub-agent's
    still-running state, plus which of `matches` come after it) and stops —
    the rest of the turn (remaining sub-agents, then synthesis) only
    continues from `resume_turn`, on a separate request.

    `tool_executor` defaults to `None` here (rather than importing
    orchestrator's real default directly) purely so it can be passed
    through untouched to `run_sub_agent`, which already knows its own
    default — this module doesn't need an opinion on what that is."""
    executor_kwargs = {} if tool_executor is None else {"tool_executor": tool_executor}
    for i, sub_agent in enumerate(matches):
        yield _sse("progress", {"stage": f"agent:{sub_agent.id} started"})
        tracer.start_span(AgentType.default, sub_agent.id, message)
        outcome = await run_sub_agent(sub_agent, message, context, llm, **executor_kwargs)

        if isinstance(outcome, SubAgentPaused):
            state.paused = outcome
            db.add(
                PendingTurnApproval(
                    turn_id=turn.id,
                    sub_agent_id=sub_agent.id,
                    tool_name=outcome.tool_call.tool_name,
                    arguments=outcome.tool_call.arguments,
                    tool_use_id=outcome.tool_use_id,
                    messages=outcome.messages,
                    guard_snapshot=outcome.guard_snapshot,
                    completed_results={
                        sid: {"result": r, "status_code": state.status_codes[sid]}
                        for sid, r in state.results.items()
                    },
                    remaining_sub_agent_ids=[sa.id for sa in matches[i + 1 :]],
                )
            )
            tracer.flush()
            yield _sse(
                "approval_required",
                {
                    "turn_id": str(turn.id),
                    "tool_name": outcome.tool_call.tool_name,
                    "arguments": outcome.tool_call.arguments,
                    "sub_agent_id": sub_agent.id,
                },
            )
            return

        tracer.conclude_span(outcome.result, outcome.status_code)
        state.results[sub_agent.id] = outcome.result
        state.status_codes[sub_agent.id] = outcome.status_code
        state.worst_status = max(state.worst_status, outcome.status_code)
        db.add(
            TurnSubAgentResult(
                turn_id=turn.id,
                sub_agent_id=sub_agent.id,
                result=outcome.result,
                status_code=outcome.status_code,
            )
        )
        yield _sse("progress", {"stage": f"agent:{sub_agent.id} done", "status": outcome.status_code})


async def _finalize(
    db: AsyncSession,
    turn: Turn,
    conversation_id: uuid.UUID,
    message: str,
    state: _FanOutState,
    llm: LLMClient,
    classifier_model: str,
    tracer: TurnTracer,
) -> AsyncIterator[dict[str, str]]:
    """Steps 7-9: exactly-one/more-than-one/zero result handling, streamed
    final answer, commit, closing SSE event. Shared by `stream_turn` and
    `resume_turn` — by the time either calls this, fan-out is done."""
    results = state.results
    worst_status = state.worst_status
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
    tracer.flush()
    await db.commit()

    yield _sse("done", {"turn_id": str(turn.id), "conversation_id": str(conversation_id)})


async def stream_turn(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    message: str,
    llm: LLMClient,
    classifier_model: str,
    tracer: TurnTracer,
    tool_executor: ToolExecutor | None = None,
) -> AsyncIterator[dict[str, str]]:
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

    tracer.start_span(AgentType.classifier, "classify", message)
    matches = await resolve_matches(message, sub_agents, llm, classifier_model)
    tracer.conclude_span(json.dumps([m.id for m in matches]))
    yield _sse("progress", {"stage": "classify:done"})

    state = _FanOutState()
    async for event in _run_matches(
        db, turn, message, context, matches, llm, tracer, state, tool_executor
    ):
        yield event

    if state.paused is not None:
        await db.commit()
        return

    async for event in _finalize(db, turn, conversation_id, message, state, llm, classifier_model, tracer):
        yield event


async def resume_turn(
    db: AsyncSession,
    pending: PendingTurnApproval,
    approved: bool,
    llm: LLMClient,
    classifier_model: str,
    tracer: TurnTracer,
    tool_executor: ToolExecutor | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Continues a turn paused by `_run_matches`, per
    docs/spec/core-agentic-loop.md step 6d. `pending` is the caller's own
    lookup (the route 404s before this is ever called if there's nothing to
    resume) — deleted here either way, since a re-pause below persists a
    fresh row rather than mutating this one."""
    turn = await db.get(Turn, pending.turn_id)
    assert turn is not None  # FK-guaranteed
    sub_agent = await get_sub_agent(db, pending.sub_agent_id)
    assert sub_agent is not None  # FK-guaranteed

    state = _FanOutState(
        results={sid: r["result"] for sid, r in pending.completed_results.items()},
        status_codes={sid: r["status_code"] for sid, r in pending.completed_results.items()},
        worst_status=max((r["status_code"] for r in pending.completed_results.values()), default=0),
    )
    remaining_ids = list(pending.remaining_sub_agent_ids)
    await db.delete(pending)

    executor_kwargs = {} if tool_executor is None else {"tool_executor": tool_executor}
    tracer.start_span(AgentType.default, sub_agent.id, turn.user_message)
    outcome = await resume_sub_agent(
        sub_agent,
        pending.tool_name,
        pending.arguments,
        pending.tool_use_id,
        pending.messages,
        pending.guard_snapshot,
        llm,
        approved,
        **executor_kwargs,
    )

    if isinstance(outcome, SubAgentPaused):
        db.add(
            PendingTurnApproval(
                turn_id=turn.id,
                sub_agent_id=sub_agent.id,
                tool_name=outcome.tool_call.tool_name,
                arguments=outcome.tool_call.arguments,
                tool_use_id=outcome.tool_use_id,
                messages=outcome.messages,
                guard_snapshot=outcome.guard_snapshot,
                completed_results={
                    sid: {"result": r, "status_code": state.status_codes[sid]}
                    for sid, r in state.results.items()
                },
                remaining_sub_agent_ids=remaining_ids,
            )
        )
        tracer.flush()
        yield _sse(
            "approval_required",
            {
                "turn_id": str(turn.id),
                "tool_name": outcome.tool_call.tool_name,
                "arguments": outcome.tool_call.arguments,
                "sub_agent_id": sub_agent.id,
            },
        )
        await db.commit()
        return

    tracer.conclude_span(outcome.result, outcome.status_code)
    state.results[sub_agent.id] = outcome.result
    state.status_codes[sub_agent.id] = outcome.status_code
    state.worst_status = max(state.worst_status, outcome.status_code)
    db.add(
        TurnSubAgentResult(
            turn_id=turn.id,
            sub_agent_id=sub_agent.id,
            result=outcome.result,
            status_code=outcome.status_code,
        )
    )
    yield _sse("progress", {"stage": f"agent:{sub_agent.id} done", "status": outcome.status_code})

    remaining_sub_agents = []
    for sub_agent_id in remaining_ids:
        remaining = await get_sub_agent(db, sub_agent_id)
        if remaining is not None:
            remaining_sub_agents.append(remaining)

    context = await _load_context(db, turn.conversation_id)
    async for event in _run_matches(
        db, turn, turn.user_message, context, remaining_sub_agents, llm, tracer, state, tool_executor
    ):
        yield event

    if state.paused is not None:
        await db.commit()
        return

    async for event in _finalize(
        db, turn, turn.conversation_id, turn.user_message, state, llm, classifier_model, tracer
    ):
        yield event


async def verify_turn(
    db: AsyncSession,
    turn_id: uuid.UUID,
    user_id: uuid.UUID,
    llm: LLMClient,
    verifier_model: str,
    tracer: TurnTracer,
) -> TurnVerification | None:
    """None means "no completed turn to verify" — the route maps that to a
    404. The verifier's assessment is its own traced span, not folded into
    the original turn's trace (see docs/spec/core-agentic-loop.md, step 11)."""
    turn = await db.get(Turn, turn_id)
    if turn is None or turn.final_response is None:
        return None

    tracer.start_trace(turn.final_response, f"verify:{turn.id}")
    tracer.start_span(AgentType.judge, "verify", turn.user_message)
    result = verify(turn.user_message, turn.final_response, llm, verifier_model)
    tracer.conclude_span(result)
    tracer.conclude_trace(result)
    tracer.flush()

    verification = TurnVerification(turn_id=turn.id, result=result, invoked_by_user_id=user_id)
    db.add(verification)
    await db.commit()
    return verification
