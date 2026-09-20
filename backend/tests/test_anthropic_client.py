"""AnthropicClient never had a dedicated test file (real SDK boundary,
tested only live) — this file only covers what's genuinely new and testable
without hitting the real API: `_render_output_for_log`'s pure logic, and
that `complete()` never raises just because Galileo isn't configured (no
active galileo_context, no credentials) — the same swallow-and-log
philosophy as TurnTracer, now also load-bearing here since every LLM call
logs a Galileo span as a side effect of the real API call."""

from dataclasses import dataclass
from typing import Any

from theshed.agents.providers.anthropic import AnthropicClient, LLMResponse, _render_output_for_log


class TestRenderOutputForLog:
    def test_uses_text_when_present(self) -> None:
        result = LLMResponse(text="the answer", tool_calls=[], stop_reason="end_turn")
        assert _render_output_for_log(result) == "the answer"

    def test_renders_tool_calls_when_there_is_no_text(self) -> None:
        result = LLMResponse(
            text=None,
            tool_calls=[{"id": "1", "name": "web_search", "arguments": {"query": "x"}}],
            stop_reason="tool_use",
        )
        assert _render_output_for_log(result) == "[tool_use: web_search({'query': 'x'})]"

    def test_falls_back_when_there_is_neither(self) -> None:
        result = LLMResponse(text=None, tool_calls=[], stop_reason="end_turn")
        assert _render_output_for_log(result) == "(no output)"


@dataclass
class _FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 5


@dataclass
class _FakeTextBlock:
    type: str
    text: str


@dataclass
class _FakeResponse:
    content: list[Any]
    stop_reason: str = "end_turn"
    usage: _FakeUsage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = _FakeUsage()


class _FakeMessages:
    def create(self, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(content=[_FakeTextBlock(type="text", text="hi there")])


class _FakeAnthropicSDKClient:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


class TestCompleteWithoutGalileoConfigured:
    def test_still_returns_the_real_response_when_galileo_span_logging_fails(self) -> None:
        client = AnthropicClient(api_key="sk-ant-fake")
        client._client = _FakeAnthropicSDKClient()  # type: ignore[assignment]

        # No active galileo_context and no real credentials in this test
        # process — get_logger_instance() inside _log_llm_span raises, and
        # complete() must still return the actual result rather than
        # letting that exception propagate.
        result = client.complete(system="be helpful", messages=[{"role": "user", "content": "hi"}], model="m")

        assert result.text == "hi there"
        assert result.tool_calls == []

    def test_records_debug_events_when_debug_is_on(self, monkeypatch) -> None:
        from theshed.debug import log as debug_log

        monkeypatch.setenv("THESHED_DEBUG", "1")
        debug_log.reset_for_tests()
        client = AnthropicClient(api_key="sk-ant-fake")
        client._client = _FakeAnthropicSDKClient()  # type: ignore[assignment]

        result = client.complete(
            system="be helpful", messages=[{"role": "user", "content": "hi"}], model="claude-haiku-4-5"
        )

        assert result.text == "hi there"
        events = debug_log.snapshot()
        assert events[0]["source"] == "llm"
        assert events[0]["event"] == "call"
        assert "claude-haiku-4-5" in events[0]["message"]
        assert events[-1]["event"] == "done"
