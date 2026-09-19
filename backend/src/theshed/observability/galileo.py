"""Galileo tracing, per docs/architecture.md and docs/spec/core-agentic-loop.md:
one Galileo session per conversation, one trace per turn, with
classify/agent/verifier spans nested underneath — and, since every LLM call
anywhere in the system flows through `AnthropicClient.complete()`, an `llm`
span (system prompt, full message history, tools offered, response, token
counts) nested under whichever of those is currently open, instrumented
there rather than here.

Built around `galileo_context` (a `ContextVar`-based context manager, not a
bare `GalileoLogger` instance held and manually threaded) — confirmed
against `cl-ai-builders`' own working integration that this is the SDK's
actual intended shape: `galileo_context.get_logger_instance()` looks up
whatever trace/span is current for THIS async task, so a span logged deep
inside `AnthropicClient.complete()` — called from classify/synthesize/
verify, none of which know or should know anything about Galileo — nests
correctly without a tracer object threaded through every pure function's
signature.

`with tracer:` wraps a turn's entire lifecycle (`stream_turn`/`resume_turn`/
`verify_turn`'s whole body, including every yield in between — a sync `with`
holds correctly across an async generator's suspension points, and
`GeneratorExit` on early termination still runs `__exit__`). Exiting always
flushes (`galileo_context.__exit__` does this itself), so pausing for
approval — which just returns out of the `with` block early — flushes
whatever was recorded, same as a normal completion; no separate explicit
flush() call is needed anywhere else.

Every method swallows and logs its own failures rather than raising:
Galileo is observability only, explicitly not part of the TDD gate (see
"Testing discipline" in docs/architecture.md) — a broken or misconfigured
Galileo connection must never take down an actual turn. A `TurnTracer`
constructed with `project=None` (the `TurnTracer(None)` used throughout the
test suite) is a full no-op: `__enter__`/`__exit__` still run normally
(so code under test that does `with tracer:` behaves the same either way),
just without ever touching the real SDK.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Self

from galileo import galileo_context, start_session
from galileo_core.schemas.logging.agent import AgentType

logger = logging.getLogger(__name__)

# One Galileo session per theshed conversation, not per turn — module-level
# and process-lifetime, same shape as cl-ai-builders' own _galileo_sessions.
# A conversation lives for as long as the process does in this dev-only
# setup; there's no eviction because there's nothing yet that would call
# for one (see docs/spec/secrets-management.md-style dev-mode caveats — a
# real deployment's session lifecycle is a separate, later concern).
_conversation_sessions: dict[str, str] = {}


def get_or_create_session_id(conversation_id: str) -> str | None:
    """None means Galileo itself is unavailable — the caller proceeds
    without a session rather than failing the turn."""
    if conversation_id not in _conversation_sessions:
        try:
            _conversation_sessions[conversation_id] = start_session(name=f"conversation:{conversation_id}")
        except Exception:
            logger.exception("Galileo start_session failed")
            return None
    return _conversation_sessions[conversation_id]


class TurnTracer:
    def __init__(self, project: str | None = None, log_stream: str | None = None) -> None:
        self._project = project
        self._log_stream = log_stream
        self._session_id: str | None = None
        self._ctx: Any = None

    @classmethod
    def create(cls, project: str, log_stream: str) -> TurnTracer:
        return cls(project, log_stream)

    def use_conversation(self, conversation_id: str) -> None:
        """Resolves (or reuses) this conversation's Galileo session. Must
        be called before entering this tracer as a context manager — a
        no-op if this tracer is already disabled (`project is None`)."""
        if self._project is None:
            return
        self._session_id = get_or_create_session_id(conversation_id)

    def __enter__(self) -> Self:
        if self._project is None:
            return self
        try:
            self._ctx = galileo_context(
                project=self._project, log_stream=self._log_stream, session_id=self._session_id
            )
            self._ctx.__enter__()
        except Exception:
            logger.exception("Galileo context entry failed — continuing without tracing this turn.")
            self._ctx = None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._ctx is None:
            return
        try:
            self._ctx.__exit__(exc_type, exc_value, traceback)
        except Exception:
            logger.exception("Galileo context exit failed")

    def _logger_instance(self) -> Any | None:
        if self._ctx is None:
            return None
        try:
            return galileo_context.get_logger_instance()
        except Exception:
            logger.exception("Galileo get_logger_instance failed")
            return None

    def start_trace(self, user_message: str, turn_id: str) -> None:
        lg = self._logger_instance()
        if lg is None:
            return
        try:
            lg.start_trace(input=user_message, name=f"turn:{turn_id}")
        except Exception:
            logger.exception("Galileo start_trace failed")

    def conclude_trace(self, output: str, status_code: int = 0) -> None:
        lg = self._logger_instance()
        if lg is None:
            return
        try:
            lg.conclude(output=output, status_code=status_code)
        except Exception:
            logger.exception("Galileo conclude_trace failed")

    def start_span(self, agent_type: AgentType, name: str, input: str) -> None:
        """`agent_type` must be a real `AgentType` member — confirmed live
        that an arbitrary string (e.g. "classify") is silently dropped by
        the SDK with no exception, no error, and no span. See
        tests/test_galileo_tracer.py for the full story."""
        lg = self._logger_instance()
        if lg is None:
            return
        try:
            lg.add_agent_span(input=input, name=name, agent_type=agent_type)
        except Exception:
            logger.exception("Galileo start_span failed")

    def conclude_span(self, output: str, status_code: int = 0) -> None:
        lg = self._logger_instance()
        if lg is None:
            return
        try:
            lg.conclude(output=output, status_code=status_code)
        except Exception:
            logger.exception("Galileo conclude_span failed")
