"""MCP client for `run.network`'s tools, per docs/prd/core-agentic-loop.md
("real tools via the existing `unifi-mcp` MCP server"). A fresh session is
opened per call rather than pooled/reused across a turn's tool loop — this
is a low-traffic, single-user home-network tool where a sub-agent typically
makes 1-3 calls a turn, and per-call sessions are far simpler than managing
a session's lifetime across a multi-round async tool loop, with no real
latency cost worth the added complexity at this scale.

`input_schema` comes back from the server as JSON Schema with a top-level
`$schema` key — stripped here since Anthropic's tool spec doesn't expect it
and it isn't meaningful to a model deciding how to call the tool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import httpx2, streamable_http_client


@asynccontextmanager
async def _session(url: str, bearer_token: str) -> AsyncIterator[ClientSession]:
    async with (
        httpx2.AsyncClient(headers={"Authorization": f"Bearer {bearer_token}"}) as http_client,
        streamable_http_client(url, http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


async def list_mcp_tools(url: str, bearer_token: str) -> list[dict[str, Any]]:
    """Anthropic-tool-spec-shaped dicts (name/description/input_schema) —
    `has_side_effects` isn't something MCP itself expresses, so the caller
    (the seed migration, matching unifi-mcp's own preview_*/confirm_*
    naming convention) decides that per tool."""
    async with _session(url, bearer_token) as session:
        result = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {k: v for k, v in tool.input_schema.items() if k != "$schema"},
            }
            for tool in result.tools
        ]


async def call_mcp_tool(url: str, bearer_token: str, name: str, arguments: dict[str, Any]) -> str:
    """Per docs/spec/core-agentic-loop.md step 6d: a tool call's error
    feeds back into the loop as an error-flagged result for the model to
    react to, not an exception — so a server-side error still returns a
    string here, just prefixed, rather than raising."""
    async with _session(url, bearer_token) as session:
        result = await session.call_tool(name, arguments)
        text = "\n".join(block.text for block in result.content if block.type == "text")
        if result.is_error:
            return f"Error calling {name}: {text or '(no error detail)'}"
        return text or "(no output)"
