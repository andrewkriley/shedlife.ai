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
        llm = FakeLLM(response_text=json.dumps(["assist"]))

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
        llm = FakeLLM(response_text=json.dumps(["build.nonexistent"]))

        matches = classify("do something", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_a_macro_category_prefix_of_the_real_id_is_filtered_out_not_matched(self) -> None:
        # Confirmed live: a real "run.network" registration got misrouted to
        # assist because the classifier returned sub_agent_id "run" (its own
        # macro_category, not the actual id) — the two-field
        # {macro_category, sub_agent_id} object format this replaced made
        # that mixup easy; the id-only array format below is the fix, but
        # this guards the validation itself regardless of how it happens.
        sub_agents = [make_sub_agent(id="run.network", macro_category="run")]
        llm = FakeLLM(response_text=json.dumps(["run"]))

        matches = classify("how many devices are on my network?", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_matches_more_than_one_sub_agent(self) -> None:
        sub_agents = [make_sub_agent(id="assist"), make_sub_agent(id="run.network", macro_category="run")]
        llm = FakeLLM(response_text=json.dumps(["assist", "run.network"]))

        matches = classify("compare today's news with my network status", sub_agents, llm, model="m")

        assert {m.sub_agent_id for m in matches} == {"assist", "run.network"}

    def test_strips_a_markdown_code_fence_before_parsing(self) -> None:
        # Confirmed live: haiku models often wrap JSON in a ```json fence
        # despite the prompt asking for "only a JSON array" — every mocked
        # test before this one used a clean string, so nothing caught it
        # until a real classifier call did.
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text='```json\n["assist"]\n```')

        matches = classify("what's the weather", sub_agents, llm, model="claude-haiku-4-5")

        assert len(matches) == 1
        assert matches[0].sub_agent_id == "assist"

    def test_strips_a_bare_code_fence_without_a_json_language_tag(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text='```\n["assist"]\n```')

        matches = classify("what's the weather", sub_agents, llm, model="claude-haiku-4-5")

        assert len(matches) == 1

    def test_malformed_json_response_yields_no_matches_not_a_crash(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text="not json at all")

        matches = classify("hello", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_a_json_object_instead_of_an_array_yields_no_matches_not_a_crash(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text=json.dumps({"sub_agent_id": "assist"}))

        matches = classify("hello", sub_agents, llm, model="claude-haiku-4-5")

        assert matches == []

    def test_a_non_string_array_item_is_skipped_not_a_crash(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text=json.dumps(["assist", {"nested": "object"}, 42]))

        matches = classify("hello", sub_agents, llm, model="claude-haiku-4-5")

        assert [m.sub_agent_id for m in matches] == ["assist"]

    def test_prompt_is_built_from_registry_not_hardcoded(self) -> None:
        sub_agents = [make_sub_agent(id="run.network", macro_category="run")]
        llm = FakeLLM(response_text="[]")

        classify("check the network", sub_agents, llm, model="claude-haiku-4-5")

        assert llm.received_system is not None
        assert "run.network" in llm.received_system

    def test_context_is_included_before_the_new_message_when_supplied(self) -> None:
        # Confirmed live: a bare follow-up ("Yes, please proceed and confirm
        # it.") to a run.network plan got classified to assist instead, and
        # assist -- never having seen the plan -- claimed no network access
        # at all. classify() previously saw only the new message, never
        # prior turns, so a confirmation with no topical words of its own
        # had nothing to route on.
        sub_agents = [make_sub_agent(id="run.network", macro_category="run")]
        llm = FakeLLM(response_text=json.dumps(["run.network"]))
        context = [
            {"role": "user", "content": "set my laptop's alias to TestAlias"},
            {"role": "assistant", "content": "Previewed the change. Shall I proceed?"},
        ]

        matches = classify(
            "Yes, please proceed and confirm it.", sub_agents, llm, model="m", context=context
        )

        assert [m.sub_agent_id for m in matches] == ["run.network"]
        assert llm.received_messages is not None
        assert llm.received_messages[0] == context[0]
        assert llm.received_messages[1] == context[1]
        assert llm.received_messages[-1] == {
            "role": "user",
            "content": "Yes, please proceed and confirm it.",
        }

    def test_no_context_supplied_behaves_exactly_as_before(self) -> None:
        sub_agents = [make_sub_agent()]
        llm = FakeLLM(response_text=json.dumps(["assist"]))

        classify("what's the weather", sub_agents, llm, model="m")

        assert llm.received_messages == [{"role": "user", "content": "what's the weather"}]
