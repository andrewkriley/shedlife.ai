"""Native OpenAI SDK wrapper. Same LLMClient shape as AnthropicClient."""

from __future__ import annotations

import json
from typing import Any, cast

from openai import OpenAI

from theshed.agents.providers.anthropic import LLMResponse

_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _is_reasoning_model(model: str) -> bool:
    return model.startswith(_REASONING_PREFIXES)


def completion_kwargs(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Chat Completions payload. Reasoning models need
    max_completion_tokens. GPT-5.x accepts reasoning_effort=none;
    o-series (o4-mini, …) rejects none and wants low/medium/high."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    converted = _to_openai_tools(tools)
    if converted:
        kwargs["tools"] = converted
    if _is_reasoning_model(model):
        kwargs["max_completion_tokens"] = 4096
        kwargs["reasoning_effort"] = "none" if model.startswith("gpt-5") else "low"
    return kwargs


class OpenAIClient:
    vendor = "openai"

    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key, timeout=60.0)
        self.models = self._client.models

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        from theshed.debug import log as debug_log

        started = debug_log.log_llm_start(self.vendor, model, tools=len(tools or []))
        try:
            response = self._client.chat.completions.create(
                **cast(Any, completion_kwargs(
                    model=model,
                    messages=_to_openai_messages(system, messages),
                    tools=tools,
                )),
            )
        except Exception as exc:
            debug_log.log_llm_error(self.vendor, model, started, exc)
            raise
        choice = response.choices[0].message
        tool_calls = []
        for call in choice.tool_calls or []:
            function = getattr(call, "function", None)
            if function is None:
                continue
            tool_calls.append(
                {
                    "id": call.id,
                    "name": function.name,
                    "arguments": _parse_arguments(function.arguments),
                }
            )
        result = LLMResponse(
            text=choice.content or None,
            tool_calls=tool_calls,
            stop_reason=str(response.choices[0].finish_reason or ""),
        )
        debug_log.log_llm_done(
            self.vendor,
            model,
            started,
            chars=len(result.text or ""),
            tools=len(result.tool_calls),
            stop_reason=result.stop_reason,
        )
        return result


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not tools:
        return []
    converted: list[dict[str, Any]] = []
    for tool in tools:
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema")
                    or tool.get("parameters")
                    or {"type": "object", "properties": {}},
                },
            }
        )
    return converted


def _to_openai_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            continue
        if role == "assistant":
            text_parts = [block["text"] for block in content if block.get("type") == "text"]
            tool_calls = [
                {
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block.get("input") or {}),
                    },
                }
                for block in content
                if block.get("type") == "tool_use"
            ]
            converted: dict[str, Any] = {
                "role": "assistant",
                "content": "\n".join(text_parts) or None,
            }
            if tool_calls:
                converted["tool_calls"] = tool_calls
            out.append(converted)
            continue
        for block in content:
            if block.get("type") == "tool_result":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": str(block.get("content") or ""),
                    }
                )
    return out
