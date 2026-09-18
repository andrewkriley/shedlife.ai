from dataclasses import dataclass
from typing import Any

from theshed.agents.providers.anthropic import LLMResponse
from theshed.agents.verifier import verify


@dataclass
class FakeLLM:
    response_text: str | None
    received_messages: list[dict[str, Any]] | None = None

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.received_messages = messages
        assert tools is None or tools == []  # the verifier never gets tools
        return LLMResponse(text=self.response_text, tool_calls=[], stop_reason="end_turn")


def test_returns_the_verifier_llms_assessment() -> None:
    llm = FakeLLM(response_text="This answer holds up — it directly addresses the question.")

    result = verify("What's the capital of France?", "Paris.", llm, model="claude-sonnet-5")

    assert result == "This answer holds up — it directly addresses the question."


def test_includes_both_the_question_and_the_answer_in_the_prompt() -> None:
    llm = FakeLLM(response_text="ok")

    verify("original question text", "the given answer text", llm, model="claude-sonnet-5")

    prompt = llm.received_messages[0]["content"]
    assert "original question text" in prompt
    assert "the given answer text" in prompt


def test_falls_back_to_a_placeholder_if_llm_returns_no_text() -> None:
    llm = FakeLLM(response_text=None)

    result = verify("q", "a", llm, model="claude-sonnet-5")

    assert result == "(verifier produced no output)"
