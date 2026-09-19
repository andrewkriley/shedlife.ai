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
from typing import Any

from theshed.agents.providers.anthropic import LLMClient
from theshed.db.models import SubAgent

CLASSIFIER_SYSTEM_PROMPT_TEMPLATE = """\
You are a routing classifier for The Shed. Given a user's message, decide which \
of the following sub-agents (if any) should handle it. A message may match more \
than one sub-agent if it genuinely spans multiple areas.

Available sub-agents:
{sub_agent_descriptions}

The conversation so far (if any) is included as prior turns before the latest \
user message. A short confirmation, correction, or continuation on its own \
("yes", "proceed", "do it", "use X instead") carries no topic of its own — route \
it to whichever sub-agent the immediately preceding assistant turn was acting as \
or asking on behalf of, not to a generic default. Only fall back to a topic-less \
match when the prior turns give no such signal either.

Respond with only a JSON array of the matching sub-agent ids, copied exactly as \
listed above (e.g. ["run.network"]) — not a macro category, not a description, \
just the id. If nothing matches, respond with an empty array []."""


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
    context: list[dict[str, Any]] | None = None,
) -> list[ClassificationMatch]:
    """Zero matches (nothing parses, or the model returns []) is a valid,
    expected result — the orchestrator's no-match fallback (routing to
    `assist`) handles it, not this function.

    `context` (prior turns of the same conversation, already loaded by the
    caller for the sub-agent call itself) is included so a terse follow-up
    ("Yes, please proceed") can be routed by what it's a follow-up *to* —
    confirmed live: without it, a bare confirmation like that carries no
    signal pointing at any sub-agent and gets dropped to the `assist`
    fallback mid-conversation, even when the prior turn was a run.network
    plan awaiting exactly that confirmation."""
    system = build_classifier_prompt(sub_agents)
    messages = [*(context or []), {"role": "user", "content": message}]
    response = llm.complete(system=system, messages=messages, model=model)
    if not response.text:
        return []

    try:
        raw_matches = json.loads(_strip_code_fence(response.text))
    except json.JSONDecodeError:
        return []

    # The model returns bare id strings now, not {macro_category,
    # sub_agent_id} objects — confirmed live that the two-field shape let a
    # real "run.network" get misrouted as sub_agent_id "run" (its own
    # macro_category prefix, not the actual id), silently degrading to a
    # no-match. macro_category itself always comes from the registry here,
    # never trusted from the model.
    if not isinstance(raw_matches, list):
        return []

    by_id = {sa.id: sa for sa in sub_agents}
    matches = []
    for sub_agent_id in raw_matches:
        if not isinstance(sub_agent_id, str):
            continue
        sub_agent = by_id.get(sub_agent_id)
        if sub_agent is not None:
            matches.append(
                ClassificationMatch(macro_category=sub_agent.macro_category, sub_agent_id=sub_agent_id)
            )
    return matches
