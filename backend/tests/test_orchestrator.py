import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from theshed.agents.orchestrator import (
    SubAgentOutcome,
    SubAgentPaused,
    resolve_matches,
    resume_sub_agent,
    run_sub_agent,
)
from theshed.agents.providers.anthropic import LLMResponse
from theshed.agents.tool_loop import LoopGuard, ToolCall
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
        extra = make_sub_agent(id="run.network", macro_category="run")
        llm = ScriptedLLM([LLMResponse(text="[]", tool_calls=[], stop_reason="end_turn")])

        matches = await resolve_matches("gibberish nonsense", [assist, extra], llm, "claude-haiku-4-5")

        assert [sa.id for sa in matches] == ["assist"]

    async def test_single_agent_short_circuits_without_a_model_call(self) -> None:
        intake = make_sub_agent(id="bootstrap.intake")

        def boom(**_kwargs: Any) -> LLMResponse:
            raise AssertionError("classifier must not be called")

        class RaisingLLM:
            complete = staticmethod(boom)

        matches = await resolve_matches("anything", [intake], RaisingLLM(), "unused")
        assert [sa.id for sa in matches] == ["bootstrap.intake"]


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
        assert llm.calls[0]["model"] == "claude-haiku-4-5"

    async def test_uses_the_model_the_turn_resolved_not_the_registry_default(self) -> None:
        assist = make_sub_agent()
        llm = ScriptedLLM(
            [LLMResponse(text="ok", tool_calls=[], stop_reason="end_turn")]
        )

        await run_sub_agent(assist, "hello", [], llm, model="gpt-5.4")

        assert llm.calls[0]["model"] == "gpt-5.4"

    async def test_side_effect_tool_call_returns_paused_instead_of_executing(self) -> None:
        risky = make_sub_agent(
            id="run.network",
            tools=[{"name": "confirm_create_firewall_policy", "has_side_effects": True}],
        )
        llm = ScriptedLLM(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[
                        {"id": "tu_1", "name": "confirm_create_firewall_policy", "arguments": {"rule": "x"}}
                    ],
                    stop_reason="tool_use",
                )
            ]
        )

        result = await run_sub_agent(risky, "lock down the network", [], llm)

        assert isinstance(result, SubAgentPaused)
        assert result.tool_call == ToolCall(
            "confirm_create_firewall_policy", {"rule": "x"}, has_side_effects=True
        )
        assert result.tool_use_id == "tu_1"
        # Confirmed live (run.network's first real tool call): Anthropic
        # rejects the next round unless the assistant's own prior turn
        # replays its tool_use block verbatim — a flat text string in its
        # place (this loop's original shape, never exercised against the
        # real API before assist had a genuinely client-executed sibling)
        # gets "content.0.type: Field required" back.
        assert result.messages[-1] == {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "confirm_create_firewall_policy",
                    "input": {"rule": "x"},
                }
            ],
        }

    async def test_a_non_side_effect_tool_calls_result_is_fed_back_with_a_proper_type(
        self,
    ) -> None:
        assist = make_sub_agent(tools=[{"name": "web_search", "has_side_effects": False}])
        llm = ScriptedLLM(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[{"id": "tu_1", "name": "web_search", "arguments": {"query": "weather"}}],
                    stop_reason="tool_use",
                ),
                LLMResponse(text="It's sunny.", tool_calls=[], stop_reason="end_turn"),
            ]
        )

        async def fake_executor(call: ToolCall) -> str:
            return "72F and sunny"

        outcome = await run_sub_agent(assist, "what's the weather", [], llm, tool_executor=fake_executor)

        assert isinstance(outcome, SubAgentOutcome)
        assert outcome.result == "It's sunny."
        second_round_messages = llm.calls[1]["messages"]
        assert second_round_messages[-1] == {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "72F and sunny"}],
        }

    async def test_context_messages_are_seeded_before_the_new_user_message(self) -> None:
        assist = make_sub_agent()
        llm = ScriptedLLM([LLMResponse(text="ok", tool_calls=[], stop_reason="end_turn")])
        context = [{"role": "user", "content": "earlier message"}, {"role": "assistant", "content": "earlier reply"}]

        await run_sub_agent(assist, "new message", context, llm)

        sent_messages = llm.calls[0]["messages"]
        assert sent_messages[0] == context[0]
        assert sent_messages[-1] == {"role": "user", "content": "new message"}


@dataclass
class FakeExecutor:
    """Records every call it's given and returns a canned result — stands in
    for the real client-side tool dispatch, which nothing implements yet."""

    result: str = "executed"
    calls: list[ToolCall] = field(default_factory=list)

    async def __call__(self, call: ToolCall) -> str:
        self.calls.append(call)
        return self.result


@pytest.mark.asyncio
class TestResumeSubAgent:
    async def test_declined_returns_a_failed_outcome_without_executing_the_tool(self) -> None:
        risky = make_sub_agent(id="run.network")
        executor = FakeExecutor()

        result = await resume_sub_agent(
            risky,
            tool_name="confirm_create_firewall_policy",
            arguments={"rule": "x"},
            tool_use_id="tu_1",
            messages=[{"role": "user", "content": "lock it down"}],
            guard_snapshot=None,
            llm=ScriptedLLM([]),
            approved=False,
        )

        assert isinstance(result, SubAgentOutcome)
        assert result.status_code == 1
        assert executor.calls == []

    async def test_approved_executes_the_tool_and_continues_the_loop(self) -> None:
        risky = make_sub_agent(id="run.network")
        executor = FakeExecutor(result="policy created")
        llm = ScriptedLLM(
            [LLMResponse(text="Done — the policy is live.", tool_calls=[], stop_reason="end_turn")]
        )

        result = await resume_sub_agent(
            risky,
            tool_name="confirm_create_firewall_policy",
            arguments={"rule": "x"},
            tool_use_id="tu_1",
            messages=[{"role": "user", "content": "lock it down"}],
            guard_snapshot=LoopGuard().snapshot(),
            llm=llm,
            approved=True,
            tool_executor=executor,
        )

        assert isinstance(result, SubAgentOutcome)
        assert result.result == "Done — the policy is live."
        assert executor.calls == [ToolCall("confirm_create_firewall_policy", {"rule": "x"}, True)]

    async def test_approved_sends_a_tool_result_referencing_the_original_tool_use_id(self) -> None:
        risky = make_sub_agent(id="run.network")
        executor = FakeExecutor(result="policy created")
        llm = ScriptedLLM([LLMResponse(text="Done.", tool_calls=[], stop_reason="end_turn")])

        await resume_sub_agent(
            risky,
            tool_name="confirm_create_firewall_policy",
            arguments={"rule": "x"},
            tool_use_id="tu_1",
            messages=[{"role": "user", "content": "lock it down"}],
            guard_snapshot=LoopGuard().snapshot(),
            llm=llm,
            approved=True,
            tool_executor=executor,
        )

        sent_messages = llm.calls[0]["messages"]
        tool_result_turn = sent_messages[-1]
        assert tool_result_turn == {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "policy created"}],
        }

    async def test_guard_state_survives_the_pause_so_a_repeat_after_resume_is_caught(self) -> None:
        risky = make_sub_agent(
            id="run.network",
            tools=[{"name": "confirm_create_firewall_policy", "has_side_effects": True}],
        )
        # Simulate: the same call already happened once before the pause.
        # has_side_effects=False here only so before_call doesn't itself
        # raise ApprovalRequired — the seen_calls key it registers doesn't
        # depend on that flag, so this seeds the same state either way.
        guard = LoopGuard()
        guard.before_call(ToolCall("confirm_create_firewall_policy", {"rule": "x"}, False))
        snapshot = guard.snapshot()

        executor = FakeExecutor()
        # After resuming, the model immediately tries the identical call again.
        llm = ScriptedLLM(
            [
                LLMResponse(
                    text=None,
                    tool_calls=[
                        {
                            "id": "tu_2",
                            "name": "confirm_create_firewall_policy",
                            "arguments": {"rule": "x"},
                        }
                    ],
                    stop_reason="tool_use",
                )
            ]
        )

        result = await resume_sub_agent(
            risky,
            tool_name="confirm_create_firewall_policy",
            arguments={"rule": "x"},
            tool_use_id="tu_1",
            messages=[{"role": "user", "content": "lock it down"}],
            guard_snapshot=snapshot,
            llm=llm,
            approved=True,
            tool_executor=executor,
        )

        assert isinstance(result, SubAgentOutcome)
        assert result.status_code == 1
        assert "epeated" in result.result
