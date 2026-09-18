import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from theshed.agents.orchestrator import resolve_matches, run_sub_agent
from theshed.agents.providers.anthropic import LLMResponse
from theshed.agents.tool_loop import ApprovalRequired
from theshed.db.models import SubAgent


def make_sub_agent(**overrides: Any) -> SubAgent:
    defaults: dict[str, Any] = {
        "id": "assist",
        "macro_category": "assist",
        "description": "General web search/fetch Q&A",
        "system_prompt": "You are helpful.",
        "tools": [],
        "default_provider": "anthropic",
        "default_model": "claude-haiku-4-5",
    }
    defaults.update(overrides)
    return SubAgent(**defaults)


@dataclass
class ScriptedLLM:
    """Returns each response in `responses` in order, one per call."""

    responses: list[LLMResponse]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "model": model, "tools": tools})
        return self.responses[len(self.calls) - 1]


@pytest.mark.asyncio
class TestResolveMatches:
    async def test_returns_classified_sub_agent(self) -> None:
        assist = make_sub_agent()
        llm = ScriptedLLM(
            [LLMResponse(text=json.dumps([{"macro_category": "assist", "sub_agent_id": "assist"}]), tool_calls=[], stop_reason="end_turn")]
        )

        matches = await resolve_matches("what's the weather", [assist], llm, "claude-haiku-4-5")

        assert [sa.id for sa in matches] == ["assist"]

    async def test_falls_back_to_assist_on_zero_matches(self) -> None:
        assist = make_sub_agent()
        llm = ScriptedLLM([LLMResponse(text="[]", tool_calls=[], stop_reason="end_turn")])

        matches = await resolve_matches("gibberish nonsense", [assist], llm, "claude-haiku-4-5")

        assert [sa.id for sa in matches] == ["assist"]


@pytest.mark.asyncio
class TestRunSubAgent:
    async def test_returns_text_when_no_tool_calls(self) -> None:
        assist = make_sub_agent()
        llm = ScriptedLLM(
            [LLMResponse(text="The weather is sunny.", tool_calls=[], stop_reason="end_turn")]
        )

        outcome = await run_sub_agent(assist, "what's the weather", [], llm)

        assert outcome.result == "The weather is sunny."
        assert outcome.status_code == 0

    async def test_side_effect_tool_call_raises_approval_required(self) -> None:
        risky = make_sub_agent(
            id="run.network",
            tools=[{"name": "confirm_create_firewall_policy", "has_side_effects": True}],
        )
        llm = ScriptedLLM(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[
                        {"id": "1", "name": "confirm_create_firewall_policy", "arguments": {"rule": "x"}}
                    ],
                    stop_reason="tool_use",
                )
            ]
        )

        with pytest.raises(ApprovalRequired):
            await run_sub_agent(risky, "lock down the network", [], llm)

    async def test_context_messages_are_seeded_before_the_new_user_message(self) -> None:
        assist = make_sub_agent()
        llm = ScriptedLLM([LLMResponse(text="ok", tool_calls=[], stop_reason="end_turn")])
        context = [{"role": "user", "content": "earlier message"}, {"role": "assistant", "content": "earlier reply"}]

        await run_sub_agent(assist, "new message", context, llm)

        sent_messages = llm.calls[0]["messages"]
        assert sent_messages[0] == context[0]
        assert sent_messages[-1] == {"role": "user", "content": "new message"}
