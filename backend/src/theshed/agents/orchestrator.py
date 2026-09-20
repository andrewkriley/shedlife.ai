"""Turn orchestration, per docs/spec/core-agentic-loop.md's Sequence.

Two sub-agents are registered: `assist` (Anthropic-native `web_search` and
`code_execution`, both server-executed — they never appear in
`LLMResponse.tool_calls`, which only surfaces client-executable `tool_use`
blocks, so an `assist` turn typically resolves in a single model call) and
`run.network` (all 29 of unifi-mcp's tools, genuinely client-executed).
Synthesis (docs/spec: more-than-one-match path) is live-reachable now that
a second sub-agent exists, not just unit-tested — a message matching both
macro categories fans out to both and combines their results.

`_execute_tool` below is only the *default* client-tool executor — a
deliberate dead end (`NotImplementedError`), since this module has no
business knowing about any particular MCP server. The real dispatcher is
built in `main.py` (currently a single unifi-mcp-backed one, since that's
the only client-tool source that exists) and threaded through
`turns/service.py` as an explicit `tool_executor` parameter, per the
`ToolExecutor` shape below — `run_sub_agent`/`resume_sub_agent` only fall
back to `_execute_tool` when no real one is supplied (e.g. missing
credentials, or a unit test with nothing to dispatch to at all).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from theshed.agents.classifier import classify
from theshed.agents.providers.anthropic import LLMClient
from theshed.agents.tool_loop import (
    ApprovalRequired,
    LoopGuard,
    MaxRoundsExceeded,
    RepeatedCallDetected,
    ToolCall,
    UnproductiveLoopDetected,
)
from theshed.db.models import SubAgent

FALLBACK_SUB_AGENT_ID = "assist"


@dataclass
class SubAgentOutcome:
    result: str
    status_code: int


@dataclass
class SubAgentPaused:
    """The loop paused before executing a `has_side_effects` tool call.
    Carries everything needed to resume later, from a separate HTTP
    request, via `resume_sub_agent` — nothing here is safe to keep only in
    memory the way a normal Python call stack would, since the pause spans
    the gap between two unrelated requests."""

    tool_call: ToolCall
    tool_use_id: str
    messages: list[dict[str, Any]]
    guard_snapshot: dict[str, Any]


SubAgentRunResult = SubAgentOutcome | SubAgentPaused
ToolExecutor = Callable[[ToolCall], Awaitable[str]]


async def resolve_matches(
    message: str,
    sub_agents: list[SubAgent],
    classifier_llm: LLMClient,
    classifier_model: str,
    context: list[dict[str, Any]] | None = None,
) -> list[SubAgent]:
    """Classify, then resolve to actual SubAgent rows. Falls back to
    `assist` on zero matches (docs/prd: no-match fallback), rather than a
    dead end."""
    if len(sub_agents) == 1:
        return list(sub_agents)

    matches = classify(message, sub_agents, classifier_llm, classifier_model, context)
    if not matches:
        fallback = next((sa for sa in sub_agents if sa.id == FALLBACK_SUB_AGENT_ID), None)
        return [fallback] if fallback else []

    by_id = {sa.id: sa for sa in sub_agents}
    return [by_id[m.sub_agent_id] for m in matches if m.sub_agent_id in by_id]


def _to_anthropic_tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in tool.items() if k != "has_side_effects"}


async def _execute_tool(call: ToolCall) -> str:
    """The fallback when no real `tool_executor` was supplied — see the
    module docstring. Reachable in practice when `main.py` couldn't build
    a real dispatcher (missing unifi-mcp credentials) or in a unit test
    that doesn't inject one."""
    raise NotImplementedError(f"No client-side executor registered for tool {call.tool_name!r}")


async def _run_loop(
    sub_agent: SubAgent,
    messages: list[dict[str, Any]],
    guard: LoopGuard,
    llm: LLMClient,
    tools: list[dict[str, Any]],
    side_effect_by_name: dict[str, bool],
    tool_executor: ToolExecutor,
    model: str,
) -> SubAgentRunResult:
    """The tool-calling loop's core, shared by a fresh start (`run_sub_agent`)
    and a resume after approval (`resume_sub_agent`) — both just differ in
    how `messages`/`guard` are seeded going in."""
    while True:
        response = llm.complete(
            system=sub_agent.system_prompt, messages=messages, model=model, tools=tools
        )

        if not response.tool_calls:
            return SubAgentOutcome(result=response.text or "(no answer produced)", status_code=0)

        # Confirmed live (the first real client-executed tool call
        # run.network ever made): Anthropic rejects the next round with
        # "content.0.type: Field required" unless the assistant's own turn
        # replays its tool_use blocks verbatim, not just any text alongside
        # them — LLMResponse.tool_calls already carries exactly what's
        # needed (id/name/arguments), just under Anthropic's own field
        # names (name/input) for a tool_use block. Never exercised against
        # the real API before now: assist's tools are both server-executed,
        # so response.tool_calls was always empty for every real run.
        assistant_content: list[dict[str, Any]] = []
        if response.text:
            assistant_content.append({"type": "text", "text": response.text})
        assistant_content.extend(
            {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]}
            for tc in response.tool_calls
        )
        messages.append({"role": "assistant", "content": assistant_content})

        tool_result_messages = []
        for tc in response.tool_calls:
            call = ToolCall(
                tool_name=tc["name"],
                arguments=tc["arguments"],
                has_side_effects=side_effect_by_name.get(tc["name"], False),
            )
            try:
                guard.before_call(call)
            except ApprovalRequired:
                return SubAgentPaused(
                    tool_call=call,
                    tool_use_id=tc["id"],
                    messages=messages,
                    guard_snapshot=guard.snapshot(),
                )
            except (MaxRoundsExceeded, RepeatedCallDetected, UnproductiveLoopDetected) as exc:
                return SubAgentOutcome(result=str(exc), status_code=1)

            result = await tool_executor(call)
            try:
                guard.after_result(result)
            except UnproductiveLoopDetected as exc:
                return SubAgentOutcome(result=str(exc), status_code=1)
            tool_result_messages.append(
                {"type": "tool_result", "tool_use_id": tc["id"], "content": result}
            )

        messages.append({"role": "user", "content": tool_result_messages})


async def run_sub_agent(
    sub_agent: SubAgent,
    user_message: str,
    context_messages: list[dict[str, Any]],
    llm: LLMClient,
    tool_executor: ToolExecutor = _execute_tool,
    model: str | None = None,
) -> SubAgentRunResult:
    guard = LoopGuard()
    messages: list[dict[str, Any]] = [*context_messages, {"role": "user", "content": user_message}]
    tools = [_to_anthropic_tool_spec(t) for t in sub_agent.tools]
    side_effect_by_name = {t["name"]: t.get("has_side_effects", False) for t in sub_agent.tools}
    chosen = model or sub_agent.default_model
    return await _run_loop(
        sub_agent, messages, guard, llm, tools, side_effect_by_name, tool_executor, chosen
    )


async def resume_sub_agent(
    sub_agent: SubAgent,
    tool_name: str,
    arguments: dict[str, Any],
    tool_use_id: str,
    messages: list[dict[str, Any]],
    guard_snapshot: dict[str, Any] | None,
    llm: LLMClient,
    approved: bool,
    tool_executor: ToolExecutor = _execute_tool,
    model: str | None = None,
) -> SubAgentRunResult:
    """Continues a sub-agent's tool loop from the point `SubAgentPaused` was
    returned, per docs/spec/core-agentic-loop.md step 6d: approved resumes
    the loop after executing the tool for real; declined ends it there —
    no further model call, per the spec's own wording ("the loop ends")."""
    if not approved:
        return SubAgentOutcome(
            result=f"The required action ({tool_name}) was declined, so it wasn't completed.",
            status_code=1,
        )

    assert guard_snapshot is not None  # only absent on the declined path, handled above
    guard = LoopGuard.restore(guard_snapshot)
    tools = [_to_anthropic_tool_spec(t) for t in sub_agent.tools]
    side_effect_by_name = {t["name"]: t.get("has_side_effects", False) for t in sub_agent.tools}

    call = ToolCall(tool_name, arguments, has_side_effects=True)
    result = await tool_executor(call)
    try:
        guard.after_result(result)
    except UnproductiveLoopDetected as exc:
        return SubAgentOutcome(result=str(exc), status_code=1)

    messages = [
        *messages,
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": result}],
        },
    ]
    return await _run_loop(
        sub_agent,
        messages,
        guard,
        llm,
        tools,
        side_effect_by_name,
        tool_executor,
        model or sub_agent.default_model,
    )
