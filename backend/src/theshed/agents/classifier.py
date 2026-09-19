"""LLM-based classifier, per docs/spec/core-agentic-loop.md.

Two-tier (macro, then sub-agent) in shape, but implemented as a single call:
the prompt is built dynamically from the registry's own descriptions, so a
new sub-agent is routable the moment it's registered — no classifier code
change. Behind a narrow function interface (not a class) so heuristic/hybrid
strategies can be swapped in later per docs/architecture.md, without
touching the orchestrator that calls this.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from theshed.agents.providers.anthropic import LLMClient
from theshed.db.models import SubAgent

CLASSIFIER_SYSTEM_PROMPT_TEMPLATE = """\
You are a routing classifier for The Shed. Given a user's message, decide which \
of the following sub-agents (if any) should handle it. A message may match more \
than one sub-agent if it genuinely spans multiple areas.

Available sub-agents:
{sub_agent_descriptions}

Respond with only a JSON array of objects, each with "macro_category" and \
"sub_agent_id", matching only sub-agents from the list above. If nothing \
matches, respond with an empty array []."""


@dataclass(frozen=True)
class ClassificationMatch:
    macro_category: str
    sub_agent_id: str


def build_classifier_prompt(sub_agents: list[SubAgent]) -> str:
    descriptions = "\n".join(
        f"- {sa.id} ({sa.macro_category}): {sa.description}" for sa in sub_agents
    )
    return CLASSIFIER_SYSTEM_PROMPT_TEMPLATE.format(sub_agent_descriptions=descriptions)


def _strip_code_fence(text: str) -> str:
    """Confirmed live: despite the prompt asking for "only a JSON array",
    haiku models routinely wrap it in a ```json fence anyway — every mocked
    test before this one used a clean string, so nothing caught it until a
    real classifier call did (and it silently degraded to zero matches:
    json.loads on a fenced string raises, and classify() correctly treats
    a parse failure as "no matches" — this just makes that failure a lot
    rarer)."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")[1:]  # drop the opening ``` or ```json line
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def classify(
    message: str,
    sub_agents: list[SubAgent],
    llm: LLMClient,
    model: str,
) -> list[ClassificationMatch]:
    """Zero matches (nothing parses, or the model returns []) is a valid,
    expected result — the orchestrator's no-match fallback (routing to
    `assist`) handles it, not this function."""
    system = build_classifier_prompt(sub_agents)
    response = llm.complete(
        system=system, messages=[{"role": "user", "content": message}], model=model
    )
    if not response.text:
        return []

    try:
        raw_matches = json.loads(_strip_code_fence(response.text))
    except json.JSONDecodeError:
        return []

    # macro_category comes from the registry, not the model's own freeform
    # guess — sub_agent_id is already validated against it below, and
    # trusting the model for this one field it could hallucinate any string
    # into serves no purpose the registry doesn't already serve correctly.
    by_id = {sa.id: sa for sa in sub_agents}
    matches = []
    for item in raw_matches:
        sub_agent_id = item.get("sub_agent_id")
        sub_agent = by_id.get(sub_agent_id)
        if sub_agent is not None:
            matches.append(
                ClassificationMatch(macro_category=sub_agent.macro_category, sub_agent_id=sub_agent_id)
            )
    return matches
