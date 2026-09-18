"""Turn orchestration, per docs/spec/core-agentic-loop.md's Sequence.

Slice-1 scope (per the approved plan): exactly one sub-agent is registered
(`assist`), so the classifier can only ever produce zero or one match —
synthesis (docs/spec: more-than-one-match path) is never reached live this
slice, though `theshed.agents.synthesis` is unit-tested directly.

`assist`'s only tool (`web_search`) is server-executed by Anthropic itself —
it never appears in `LLMResponse.tool_calls` (that only surfaces
client-executable `tool_use` blocks), so this slice's real runs typically
resolve in a single model call. The client-tool-execution path
(`_execute_tool`) still exists and is exercised by the loop-guard's safety
nets, because `run.network`/`build` (MCP-based, client-executed tools) are
next.
"""

from __future__ import annotations

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


async def resolve_matches(
    message: str,
    sub_agents: list[SubAgent],
    classifier_llm: LLMClient,
    classifier_model: str,
) -> list[SubAgent]:
    """Classify, then resolve to actual SubAgent rows. Falls back to
    `assist` on zero matches (docs/prd: no-match fallback), rather than a
    dead end."""
    matches = classify(message, sub_agents, classifier_llm, classifier_model)
    if not matches:
        fallback = next((sa for sa in sub_agents if sa.id == FALLBACK_SUB_AGENT_ID), None)
        return [fallback] if fallback else []

    by_id = {sa.id: sa for sa in sub_agents}
    return [by_id[m.sub_agent_id] for m in matches if m.sub_agent_id in by_id]


def _to_anthropic_tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in tool.items() if k != "has_side_effects"}


async def _execute_tool(call: ToolCall) -> str:
    """Client-executed tool dispatch. Nothing routes here yet in this
    slice — `assist`'s web_search is server-executed by Anthropic, so this
    is only reachable once an MCP-based sub-agent (run.network) exists."""
    raise NotImplementedError(f"No client-side executor registered for tool {call.tool_name!r}")


async def run_sub_agent(
    sub_agent: SubAgent,
    user_message: str,
    context_messages: list[dict[str, Any]],
    llm: LLMClient,
) -> SubAgentOutcome:
    guard = LoopGuard()
    messages: list[dict[str, Any]] = [*context_messages, {"role": "user", "content": user_message}]
    tools = [_to_anthropic_tool_spec(t) for t in sub_agent.tools]
    side_effect_by_name = {t["name"]: t.get("has_side_effects", False) for t in sub_agent.tools}

    while True:
        response = llm.complete(
            system=sub_agent.system_prompt,
            messages=messages,
            model=sub_agent.default_model,
            tools=tools,
        )

        if not response.tool_calls:
            return SubAgentOutcome(result=response.text or "(no answer produced)", status_code=0)

        messages.append({"role": "assistant", "content": response.text or ""})
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
                raise
            except (MaxRoundsExceeded, RepeatedCallDetected, UnproductiveLoopDetected) as exc:
                return SubAgentOutcome(result=str(exc), status_code=1)

            result = await _execute_tool(call)
            guard.after_result(result)
            tool_result_messages.append({"tool_use_id": tc["id"], "content": result})

        messages.append({"role": "user", "content": tool_result_messages})
