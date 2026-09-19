"""Confirmed live: theshed's spans never showed up as children of their
trace in the real Galileo dashboard, despite no errors anywhere — every
`TurnTracer` method swallows and logs its own failures, and the SDK itself
raised nothing either. Root cause, found by an isolated repro against the
real API: `start_span` was passed `agent_type="classify"` / `"agent"` /
`"verifier"` — arbitrary strings, none of which are valid
`galileo_core.schemas.logging.agent.AgentType` members (`default`,
`planner`, `react`, `reflection`, `router`, `classifier`, `supervisor`,
`judge`). The SDK silently drops a span with an unrecognized agent_type
instead of raising — confirmed by the same repro rerun with a valid value,
which attached correctly.

These tests guard the fix at the type level: `start_span` only accepts a
real `AgentType`, so passing an arbitrary string is now a type error, not a
runtime no-op."""

from dataclasses import dataclass, field
from typing import Any

from galileo_core.schemas.logging.agent import AgentType

from theshed.observability.galileo import TurnTracer


@dataclass
class FakeGalileoLogger:
    """Records every call instead of hitting the real API — this file tests
    that TurnTracer forwards the right values, not that Galileo itself
    behaves a certain way."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def start_session(self, **kwargs: Any) -> None:
        self.calls.append(("start_session", kwargs))

    def start_trace(self, **kwargs: Any) -> None:
        self.calls.append(("start_trace", kwargs))

    def add_agent_span(self, **kwargs: Any) -> None:
        self.calls.append(("add_agent_span", kwargs))

    def conclude(self, **kwargs: Any) -> None:
        self.calls.append(("conclude", kwargs))

    def flush(self) -> None:
        self.calls.append(("flush", {}))


class TestStartSpan:
    def test_forwards_a_real_agent_type_enum_member_unchanged(self) -> None:
        fake = FakeGalileoLogger()
        tracer = TurnTracer(fake)  # type: ignore[arg-type]

        tracer.start_span(AgentType.classifier, "classify", "some input")

        assert fake.calls == [
            ("add_agent_span", {"input": "some input", "name": "classify", "agent_type": AgentType.classifier})
        ]

    def test_does_nothing_when_the_underlying_logger_is_none(self) -> None:
        tracer = TurnTracer(None)

        tracer.start_span(AgentType.default, "assist", "some input")  # no raise
