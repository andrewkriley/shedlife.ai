"""Independent verifier, per docs/architecture.md ("Independent verifier")
and docs/spec/core-agentic-loop.md. A post-synthesis check with no domain
bias of its own — no tools, reviews the final answer against the original
question. Manually invoked this phase; the future auto-trigger hook
(gated on has_side_effects) is documented, not built here."""

from __future__ import annotations

from theshed.agents.providers.anthropic import LLMClient

VERIFIER_SYSTEM_PROMPT = """\
You are an independent reviewer with no stake in the answer below — you did not \
produce it and have no domain expertise of your own to defend. Check it against the \
original question: does it actually answer what was asked? Does anything in it look \
unsupported, inconsistent, or like it's papering over a gap? Be concise. If the \
answer holds up, say so plainly rather than manufacturing a concern."""


def verify(original_message: str, final_response: str, llm: LLMClient, model: str) -> str:
    prompt = f"Original question:\n{original_message}\n\nAnswer given:\n{final_response}"
    response = llm.complete(
        system=VERIFIER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        model=model,
    )
    return response.text or "(verifier produced no output)"
