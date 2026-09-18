import json
from dataclasses import dataclass, field
from typing import Any

from theshed.agents.classifier import build_classifier_prompt, classify
from theshed.agents.providers.anthropic import LLMResponse
from theshed.db.models import SubAgent


def make_sub_agent(id: str = "assist", macro_category: str = "assist") -> SubAgent:
    return SubAgent(
        id=id,
        macro_category=macro_category,
        description="General web search/fetch Q&A",
        system_prompt="You are a helpful assistant.",
        tools=[],
        default_provider="anthropic",
        default_model="claude-haiku-4-5",
    )


@dataclass
class FakeLLM:
    """Implements the LLMClient protocol structurally — no inheritance."""

    response_text: str
    received_system: str | None = field(default=None, init=False)
    received_messages: list[dict[str, Any]] | None = field(default=None, init=False)

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.received_system = system
        self.received_messages = messages
        return LLMResponse(text=self.response_text, tool_calls=[], stop_reason="end_turn")


class TestBuildClassifierPrompt:
    def test_includes_every_sub_agent_description(self) -> None:
        sub_agents = [make_sub_agent(id="assist"), make_sub_agent(id="run.network", macro_category="run")]
        prompt = build_classifier_prompt(sub_agents)
        assert "assist" in prompt
        assert "run.network" in prompt
        assert "General web search/fetch Q&A" in prompt


class TestClassify:
    def test_returns_matches_from_valid_json_response(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text=json.dumps([{"macro_category": "assist", "sub_agent_id": "assist"}]))

        matches = classify("what's the weather", sub_agents, llm, model="claude-haiku-4-5")

        assert len(matches) == 1
        assert matches[0].sub_agent_id == "assist"
        assert matches[0].macro_category == "assist"

    def test_empty_array_response_yields_no_matches(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text="[]")

        matches = classify("gibberish", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_hallucinated_sub_agent_id_is_filtered_out(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(
            response_text=json.dumps([{"macro_category": "build", "sub_agent_id": "build.nonexistent"}])
        )

        matches = classify("do something", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_malformed_json_response_yields_no_matches_not_a_crash(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text="not json at all")

        matches = classify("hello", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_prompt_is_built_from_registry_not_hardcoded(self) -> None:
        sub_agents = [make_sub_agent(id="run.network", macro_category="run")]
        llm = FakeLLM(response_text="[]")

        classify("check the network", sub_agents, llm, model="claude-haiku-4-5")

        assert llm.received_system is not None
        assert "run.network" in llm.received_system
