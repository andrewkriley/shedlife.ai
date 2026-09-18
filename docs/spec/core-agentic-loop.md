# Core Agentic Loop — SPEC

Status: draft, technical design for
[`../prd/core-agentic-loop.md`](../prd/core-agentic-loop.md). References
[`../architecture.md`](../architecture.md) (portable pattern) and
[`../stack.md`](../stack.md) (reference technologies).

## Actors / components

- **User** — via the chat UI (React/TypeScript/Vite frontend).
- **API backend** (FastAPI) — owns the turn lifecycle.
- **Classifier** — LLM-based, cheap/fast model, prompt built dynamically from the
  sub-agent registry's descriptions.
- **Sub-agent registry** — Postgres-backed; one row per sub-agent (see Data).
- **Sub-agent executor** — runs one sub-agent's tool-calling loop against its scoped
  tools and resolved provider/model.
- **Synthesis step** — an LLM call with no tools, combining more than one sub-agent's
  results into one answer; skipped when exactly one sub-agent matched.
- **Verifier** — independent, post-synthesis, no domain bias; manually invoked this
  phase (UX not yet designed — see Open Items).
- **Provider abstraction** — native Anthropic/OpenAI SDKs; LiteLLM gateway in front of
  local runtimes (vLLM, Ollama) only.
- **Secrets client** — fetches credentials from the secrets backend via machine
  identity at call time; nothing cached beyond a call's lifetime.
- **Observability** — Galileo tracing, one session per conversation.

## Sequence (happy path)

1. User sends a message via the chat UI.
2. The API backend opens a turn. **Session/conversation state handling is an open
   question (see PRD) — this step is a placeholder pending that design.**
3. A Galileo trace starts; a `supervisor` span opens for the turn.
4. The classifier runs (one cheap-model call) against the message and the registry's
   current descriptions, returning zero or more `(macro, sub_agent_id)` matches. A
   `classify` span records the call and its result.
5. **Zero matches**: PRD open question (no-match fallback) — behavior not yet decided;
   this step is a placeholder.
6. **One or more matches**, sequentially (this phase — see PRD non-goals on
   parallelism): for each matched sub-agent —
   a. Resolve its provider/model (registry default, or an operator override from the
      settings surface).
   b. Open an `agent` span for this sub-agent.
   c. Run its tool-calling loop: call the model with its scoped tools; if it requests a
      tool call, execute it (a `tool` span per call) and feed the result back; repeat
      up to a turn cap. Two safety nets, mirroring the reference pattern in
      `architecture.md`'s inspiration: a max-turn cap, and a guard that stops on an
      identical repeated tool call.
   d. **Error handling within this loop (a tool call failing, the LLM API erroring) is
      a PRD open question** — not yet designed; this step assumes the happy path.
   e. Close the sub-agent's span with its result and status code.
7. **Exactly one match**: that sub-agent's result is the turn's final answer — no
   synthesis call.
8. **More than one match**: the synthesis step combines all matched sub-agents'
   results (no tools, one LLM call) into one answer. **Partial-failure behavior (one
   sub-agent errored, others succeeded) is a PRD open question** — not yet designed.
9. The response is returned to the chat UI. **Streaming vs. a single complete response
   is a PRD open question** — the interface below is provisional pending that
   decision.
10. The `supervisor` span closes; the trace concludes.
11. *(Optional, user-invoked, any time after step 10)*: the user triggers the verifier
    against this turn — **invocation UX is a PRD open question**. The verifier reviews
    the final answer against the original message, with no domain-scoped tools of its
    own, and returns an assessment as its own traced span, not folded into the
    original trace.

## Data

### Sub-agent registry (Postgres)

| Field | Notes |
|---|---|
| `id` | `<macro>.<name>`, e.g. `run.network` |
| `macro_category` | `assist` \| `build` \| `run` |
| `description` | One line; what the classifier's prompt is built from |
| `system_prompt` | This sub-agent's system prompt |
| `tools` | Scoped tool set (MCP tool names / references) |
| `tools[].has_side_effects` | Per-tool flag; feeds the future verifier auto-trigger hook (not enforced as a gate this phase — metadata only) |
| `default_provider` / `default_model` | Registry default; overridable via the settings surface |
| `provenance` | `manual` \| `declared` \| `discovered` \| `provisioned` — same field as the host/service registry in `architecture.md`; a sub-agent is a registry entry like any other |

### Turn / conversation state

**Not designed** — placeholder pending the PRD's open question on session/conversation
state. Whatever shape this takes, it needs to support: multiple sub-agent results per
turn, the turn's final (possibly synthesized) answer, and a link to its Galileo trace
for the verifier to reference later.

## Interfaces

**Provisional**, pending the streaming decision:

- `POST /turns` — submit a message, get back a turn result (shape depends on the
  streaming decision: a single JSON response, or a stream of events).
- Settings surface (REST): list live providers/models; list sub-agents; bulk-assign a
  provider/model to a selected set of sub-agents.

## Security model

- **Tool scoping is strictly enforced**: a sub-agent's executor only has access to the
  tools declared in its own registry row — not the full tool catalog, not another
  sub-agent's tools.
- `has_side_effects` is metadata only this phase — it does not currently gate or block
  any action; it exists so the future auto-trigger hook (PRD non-goal, `architecture.md`
  roadmap) doesn't require a schema change when it's built.
- Secrets are fetched at call time via machine identity, never cached to disk, per the
  secrets pattern in `architecture.md`.

## Open items

Mirrors the PRD's Open Questions — none of these are designed yet, all are real gaps,
not just documentation debt:

- Conversation/session state model.
- Error handling within a turn (single tool/LLM failure, partial fan-out failure).
- Verifier invocation UX.
- Streaming vs. synchronous response (blocks finalizing the `/turns` interface above).
- No-match classifier fallback.
