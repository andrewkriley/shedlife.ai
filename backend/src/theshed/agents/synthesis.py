"""Synthesis: combines more than one matched sub-agent's results into one
answer, per docs/spec/core-agentic-loop.md. A pure function — no LLM call
of its own signature-wise; the caller supplies whatever `LLMClient` it's
using. Not reachable through the live system in this slice (exactly one
sub-agent is registered, so the classifier can never produce more than one
match) — exercised directly here with fake multi-result input instead.
"""

from __future__ import annotations

from theshed.agents.providers.anthropic import LLMClient

SYNTHESIS_SYSTEM_PROMPT = """\
You are combining findings from multiple specialized sub-agents into one clear, \
unified answer for the user. Each sub-agent already gathered real information for \
its part of the question. Do not call any tools — just synthesize their findings \
into a single well-organized answer that directly addresses the user's original \
question. If a sub-agent's result indicates it failed, acknowledge the gap honestly \
rather than omitting it."""


def synthesize(
    original_message: str,
    results_by_sub_agent: dict[str, str],
    llm: LLMClient,
    model: str,
) -> str:
    findings = "\n\n".join(
        f"## {sub_agent_id}\n{result}" for sub_agent_id, result in results_by_sub_agent.items()
    )
    prompt = f"Original question: {original_message}\n\n{findings}"
    response = llm.complete(
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        model=model,
    )
    return response.text or findings
