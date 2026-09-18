"""Tool-calling loop safety nets, per docs/spec/core-agentic-loop.md and the
"Loop prevention and side-effect approval" principle in docs/architecture.md.

Three independent mechanisms, all deterministic and cheap (no embeddings, no
extra LLM calls):

- a max-round cap
- a repeated-call guard on *canonicalized* arguments (not raw exact match)
- unproductive-result tracking over the last K tool results

Plus a hard pre-execution gate: a tool call flagged `has_side_effects` pauses
the loop rather than executing, until explicitly approved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def canonicalize_arguments(arguments: dict[str, Any]) -> str:
    """Trim string values, sort keys, and normalize types so
    cosmetically-different-but-identical calls compare equal."""

    def _normalize(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            return {k: _normalize(v) for k, v in sorted(value.items())}
        if isinstance(value, list):
            return [_normalize(v) for v in value]
        return value

    normalized = _normalize(arguments)
    return json.dumps(normalized, sort_keys=True)


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    has_side_effects: bool = False


class MaxRoundsExceeded(Exception):
    pass


class RepeatedCallDetected(Exception):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Repeated identical call to {tool_name!r} — the model may be stuck.")


class UnproductiveLoopDetected(Exception):
    """Raised when the last K tool results were all effectively the same
    non-answer, regardless of whether the calls themselves varied."""


class ApprovalRequired(Exception):
    """Raised to pause the loop before executing a has_side_effects tool
    call. The caller (orchestrator) catches this, emits an SSE
    `approval_required` event, and resumes via a fresh call once approved."""

    def __init__(self, call: ToolCall) -> None:
        self.call = call
        super().__init__(f"Approval required before calling {call.tool_name!r}.")


@dataclass
class LoopGuard:
    """Tracks state across one sub-agent's tool-calling loop. One instance
    per turn per sub-agent — not shared across turns or sub-agents."""

    max_rounds: int = 8
    unproductive_window: int = 3

    _round: int = field(default=0, init=False)
    _seen_calls: set[tuple[str, str]] = field(default_factory=set, init=False)
    _recent_results: list[str] = field(default_factory=list, init=False)

    def before_call(self, call: ToolCall) -> None:
        """Call before executing a tool call. Raises if the call should not
        proceed — either because a safety net tripped, or because it needs
        approval first."""
        self._round += 1
        if self._round > self.max_rounds:
            raise MaxRoundsExceeded(f"Exceeded {self.max_rounds} rounds without a final answer.")

        key = (call.tool_name, canonicalize_arguments(call.arguments))
        if key in self._seen_calls:
            raise RepeatedCallDetected(call.tool_name)
        self._seen_calls.add(key)

        if call.has_side_effects:
            raise ApprovalRequired(call)

    def after_result(self, result: str) -> None:
        """Call after a tool call executes successfully, with its result."""
        self._recent_results.append(result)
        window = self._recent_results[-self.unproductive_window :]
        if len(window) == self.unproductive_window and len(set(window)) == 1:
            raise UnproductiveLoopDetected(
                f"Last {self.unproductive_window} tool results were identical — "
                "no progress despite varying calls."
            )
