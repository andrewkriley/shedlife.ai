from dataclasses import dataclass
from typing import Any

from theshed.agents.providers.anthropic import LLMResponse
from theshed.agents.synthesis import synthesize


@dataclass
class FakeLLM:
    response_text: str | None

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        return LLMResponse(text=self.response_text, tool_calls=[], stop_reason="end_turn")


def test_combines_multiple_results_into_llm_synthesized_answer() -> None:
    llm = FakeLLM(response_text="Combined: network is fine, and your build passed.")

    answer = synthesize(
        "is the network ok and did my build pass",
        {"run.network": "Network is healthy.", "build.gitlab": "Build passed."},
        llm,
        model="claude-sonnet-5",
    )

    assert answer == "Combined: network is fine, and your build passed."


def test_falls_back_to_raw_findings_if_llm_returns_no_text() -> None:
    llm = FakeLLM(response_text=None)

    answer = synthesize(
        "question",
        {"assist": "some finding"},
        llm,
        model="claude-sonnet-5",
    )

    assert "some finding" in answer


def test_acknowledges_a_failed_sub_agent_rather_than_silently_dropping_it() -> None:
    # Verifies the *input contract*: a failed sub-agent's result is passed through
    # like any other, not filtered out before synthesis sees it.
    captured: dict[str, Any] = {}

    @dataclass
    class CapturingLLM:
        def complete(
            self,
            *,
            system: str,
            messages: list[dict[str, Any]],
            model: str,
            tools: list[dict[str, Any]] | None = None,
        ) -> LLMResponse:
            captured["messages"] = messages
            return LLMResponse(text="ok", tool_calls=[], stop_reason="end_turn")

    synthesize(
        "question",
        {"run.network": "Failed: unifi-mcp unreachable.", "assist": "Found an answer."},
        CapturingLLM(),
        model="claude-sonnet-5",
    )

    prompt_content = captured["messages"][0]["content"]
    assert "Failed: unifi-mcp unreachable." in prompt_content
