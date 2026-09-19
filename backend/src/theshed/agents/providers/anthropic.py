"""Native Anthropic SDK wrapper, per docs/stack.md ("Model providers" — cloud
providers called via their own SDKs, full feature fidelity, not flattened
through a compatibility layer).

Exposes `LLMClient`, a minimal structural interface (a `Protocol`, not a base
class) so classifier/orchestrator/synthesis code depends on the shape, not
this specific implementation — a test substitutes a fake with no inheritance
needed, and a future provider (OpenAI, or a LiteLLM-routed local model) is a
sibling implementing the same shape.

`complete()` logs an `llm`-type Galileo span for every call — the system
prompt, full message history, tools on offer, raw response, and token
counts, matching cl-ai-builders' own `call_anthropic` (confirmed against it
as the reference for what theshed's traces were missing entirely). This is
the ONE place instrumented rather than classify/synthesize/verify/the
orchestrator's tool loop themselves, specifically so those stay
Galileo-agnostic pure functions — every LLM call anywhere in the system
already flows through here regardless of which of them made it, and
`galileo_context.get_logger_instance()` nests the span under whatever
trace/span is current for the caller without needing one threaded through
as a parameter. Swallows and logs its own failures, same as `TurnTracer` —
a broken Galileo connection must never break the actual model call.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol, cast

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[dict[str, Any]]  # [{"id": ..., "name": ..., "arguments": {...}}]
    stop_reason: str


class LLMClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...


def _render_output_for_log(result: LLMResponse) -> str:
    if result.text:
        return result.text
    if result.tool_calls:
        calls = ", ".join(f"{tc['name']}({tc['arguments']})" for tc in result.tool_calls)
        return f"[tool_use: {calls}]"
    return "(no output)"


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        # Exposed so callers outside the LLMClient shape (the settings
        # surface's live models-list, per docs/spec/core-agentic-loop.md)
        # can reach the SDK client without this class growing methods no
        # turn/synthesis call site needs.
        self.models = self._client.models

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        # The SDK's `messages`/`tools` params are typed against its own
        # narrow TypedDicts; our LLMClient interface deliberately keeps
        # plain dicts at this boundary (see the module docstring — call
        # sites depend on the shape, not the SDK's types). Cast rather than
        # thread the SDK's exact types through classifier/orchestrator/
        # synthesis, which shouldn't need to know about them.
        start = time.monotonic()
        response = self._client.messages.create(
            model=model,
            system=system,
            messages=cast(Any, messages),
            tools=cast(Any, tools or []),
            max_tokens=4096,
        )
        duration_ns = int((time.monotonic() - start) * 1e9)
        text = "".join(block.text for block in response.content if block.type == "text")
        tool_calls = [
            {"id": block.id, "name": block.name, "arguments": block.input}
            for block in response.content
            if block.type == "tool_use"
        ]
        result = LLMResponse(
            text=text or None, tool_calls=tool_calls, stop_reason=str(response.stop_reason)
        )
        self._log_llm_span(system, messages, model, tools, result, response, duration_ns)
        return result

    def _log_llm_span(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None,
        result: LLMResponse,
        response: Any,
        duration_ns: int,
    ) -> None:
        try:
            from galileo import galileo_context

            galileo_context.get_logger_instance().add_llm_span(
                input=[{"role": "system", "content": system}, *messages],
                output=_render_output_for_log(result),
                model=model,
                name="anthropic",
                tools=tools or None,
                num_input_tokens=response.usage.input_tokens,
                num_output_tokens=response.usage.output_tokens,
                duration_ns=duration_ns,
            )
        except Exception:
            logger.exception("Galileo LLM span logging failed")
