"""Native Anthropic SDK wrapper, per docs/stack.md ("Model providers" — cloud
providers called via their own SDKs, full feature fidelity, not flattened
through a compatibility layer).

Exposes `LLMClient`, a minimal structural interface (a `Protocol`, not a base
class) so classifier/orchestrator/synthesis code depends on the shape, not
this specific implementation — a test substitutes a fake with no inheritance
needed, and a future provider (OpenAI, or a LiteLLM-routed local model) is a
sibling implementing the same shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

import anthropic


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


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

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
        response = self._client.messages.create(
            model=model,
            system=system,
            messages=cast(Any, messages),
            tools=cast(Any, tools or []),
            max_tokens=4096,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        tool_calls = [
            {"id": block.id, "name": block.name, "arguments": block.input}
            for block in response.content
            if block.type == "tool_use"
        ]
        return LLMResponse(
            text=text or None, tool_calls=tool_calls, stop_reason=str(response.stop_reason)
        )
