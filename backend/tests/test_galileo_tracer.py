"""Confirmed live, across two separate investigations:

1. Spans never showed up as children of their trace, despite no errors
   anywhere. Root cause: `start_span` was passed `agent_type="classify"` /
   `"agent"` / `"verifier"` — arbitrary strings, none of which are valid
   `galileo_core.schemas.logging.agent.AgentType` members (`default`,
   `planner`, `react`, `reflection`, `router`, `classifier`, `supervisor`,
   `judge`). The SDK silently drops a span with an unrecognized
   agent_type — no exception. `start_span` now takes a real `AgentType`,
   so this is a type error going forward, not a runtime no-op — enforced
   by mypy, not re-tested here at runtime.

2. Traces never had a *session* worth looking at — a new Galileo session
   was created on every single turn instead of one per conversation
   (`cl-ai-builders`' own working integration groups by conversation via
   a module-level id cache; theshed's tracer never did). And a bare
   `GalileoLogger` instance, manually threaded through the turn lifecycle
   and never wrapped in `galileo_context`, gives `AnthropicClient` (deep
   inside classify/synthesize/verify, none of which know about tracing at
   all) nothing to nest an `llm` span against — `galileo_context` is a
   `ContextVar`-based context manager specifically so any code in the same
   async task can log into whatever's "current" without a tracer object
   passed down to it.

This file tests `TurnTracer`'s own contract — that `start_span` forwards
`agent_type` unchanged, that a `project=None` tracer runs `__enter__`/
`__exit__` as normal no-ops (so code under test that does `with tracer:`
behaves identically whether or not Galileo is actually configured), and
that `use_conversation` caches one session id per conversation. It does not
hit the real Galileo API — `galileo_context.get_logger_instance` is
patched so these run without credentials."""

from typing import Any
from unittest.mock import MagicMock, patch

from galileo_core.schemas.logging.agent import AgentType

from theshed.observability import galileo as galileo_module
from theshed.observability.galileo import TurnTracer, get_or_create_session_id


class TestNoOpTracer:
    def test_enter_and_exit_do_not_raise(self) -> None:
        with TurnTracer(None):
            pass  # no exception

    def test_every_method_is_a_safe_no_op(self) -> None:
        tracer = TurnTracer(None)
        with tracer:
            tracer.start_trace("hi", "turn-1")
            tracer.start_span(AgentType.classifier, "classify", "hi")
            tracer.conclude_span("result")
            tracer.conclude_trace("final")
        # no exception anywhere above is the whole test

    def test_use_conversation_is_a_no_op_without_a_project(self) -> None:
        tracer = TurnTracer(None)
        tracer.use_conversation("some-conversation-id")  # no exception


class TestStartSpanForwarding:
    def test_forwards_a_real_agent_type_enum_member_unchanged(self) -> None:
        fake_logger: Any = MagicMock()
        with patch.object(galileo_module.galileo_context, "get_logger_instance", return_value=fake_logger):
            tracer = TurnTracer("proj", "stream")
            with tracer:
                tracer.start_span(AgentType.classifier, "classify", "some input")

        fake_logger.add_agent_span.assert_called_once_with(
            input="some input", name="classify", agent_type=AgentType.classifier
        )


class TestGetOrCreateSessionId:
    def test_caches_one_session_id_per_conversation(self) -> None:
        galileo_module._conversation_sessions.clear()
        with patch.object(galileo_module, "start_session", return_value="session-abc") as mock_start:
            first = get_or_create_session_id("conv-1")
            second = get_or_create_session_id("conv-1")

        assert first == "session-abc"
        assert second == "session-abc"
        mock_start.assert_called_once()  # the second call reused the cache, didn't call start_session again

    def test_a_different_conversation_gets_its_own_session(self) -> None:
        galileo_module._conversation_sessions.clear()
        with patch.object(galileo_module, "start_session", side_effect=["session-a", "session-b"]):
            first = get_or_create_session_id("conv-a")
            second = get_or_create_session_id("conv-b")

        assert first == "session-a"
        assert second == "session-b"

    def test_returns_none_without_raising_when_galileo_is_unavailable(self) -> None:
        galileo_module._conversation_sessions.clear()
        with patch.object(galileo_module, "start_session", side_effect=RuntimeError("unreachable")):
            result = get_or_create_session_id("conv-x")

        assert result is None
