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
- **Object storage (MinIO)** — self-hosted, S3-compatible; another platform-layer
  Flux-managed workload, same deployment pattern as the database/cache. Holds both
  user-uploaded and sub-agent-generated attachments.

## Sequence (happy path)

0. *(Optional, before step 1)*: if the message includes an image, the client uploads it
   via the attachments endpoint first and gets back a reference, included when the
   turn is submitted.
1. User sends a message (plus any attachment references) into a conversation via the
   chat UI (an existing conversation, or a new one), opening an SSE connection for the
   response.
2. The API backend opens a turn within that conversation, and loads context: the last
   N turns' `(user message, final response)` pairs, N a tunable recency-cap default
   (older turns dropped this phase — no summarization yet).
3. A Galileo trace starts for this turn; a `supervisor` span opens. If this is the
   conversation's first turn, a new Galileo session starts too — otherwise the trace
   joins the conversation's existing session.
4. The classifier runs (one cheap-model call) against the message, the loaded context,
   and the registry's current descriptions, returning zero or more `(macro,
   sub_agent_id)` matches. A `classify` span records the call and its result. An SSE
   `progress` event (`classify: done`) is emitted.
5. **Zero matches**: PRD open question (no-match fallback) — behavior not yet decided;
   this step is a placeholder.
6. **One or more matches**, sequentially (this phase — see PRD non-goals on
   parallelism): for each matched sub-agent — an SSE `progress` event
   (`agent:<id> started`) is emitted, then:
   a. Resolve its provider/model (registry default, or an operator override from the
      settings surface).
   b. Open an `agent` span for this sub-agent.
   c. Seed its tool-calling loop's message list with the same loaded context from step
      2, followed by the current user message (and any attachments, for a sub-agent
      whose model supports image input).
   d. Run its tool-calling loop: call the model with its scoped tools; if it requests a
      tool call, execute it (a `tool` span per call) and feed the result back; repeat
      up to a turn cap. Two safety nets, mirroring the reference pattern in
      `architecture.md`'s inspiration: a max-turn cap, and a guard that stops on an
      identical repeated tool call. If a tool call produces an attachment (a diagram, a
      screenshot), it's stored via the attachments endpoint and referenced in the
      sub-agent's result, not inlined.
   e. **Error handling within this loop (a tool call failing, the LLM API erroring) is
      a PRD open question** — not yet designed; this step assumes the happy path.
   f. Close the sub-agent's span with its result and status code. An SSE `progress`
      event (`agent:<id> done`) is emitted.
7. **Exactly one match**: that sub-agent's result is the turn's final answer, streamed
   token-by-token over the same SSE connection as it's produced — no synthesis call.
8. **More than one match**: an SSE `progress` event (`synthesis started`) is emitted;
   the synthesis step combines all matched sub-agents' results (no tools, one LLM
   call) into one answer, streamed token-by-token as it's produced. **Partial-failure
   behavior (one sub-agent errored, others succeeded) is a PRD open question** — not
   yet designed.
9. A final SSE event carries the completed answer's metadata (any attachment
   references, the turn id) and closes the stream.
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

### Conversation / turn (Postgres)

| Table | Key fields |
|---|---|
| `conversations` | `id`, `user_id` (owner, per the multi-user-ready data model), `galileo_session_id`, `created_at` |
| `turns` | `id`, `conversation_id`, `user_message`, `final_response`, `galileo_trace_id`, `created_at` |
| `turn_sub_agent_results` | `turn_id`, `sub_agent_id`, `result`, `status_code` — one row per sub-agent matched in that turn, for the verifier and for debugging; **not** replayed as future context (only `turns.final_response` is) |
| `attachments` | `id`, `owner_user_id`, `source` (`upload` \| `generated`), `content_type`, `size_bytes`, `storage_key` (MinIO object key), `created_at` |
| `turn_attachments` | `turn_id`, `attachment_id`, `role` (`input` \| `output`) — join table linking attachments to the turn they were submitted with or produced by |

Context for a new turn = the owning conversation's last N `turns`, each reduced to
`(user_message, final_response)` — `turn_sub_agent_results` stays out of the replayed
context, consistent with the PRD's reasoning (internal detail belongs to that turn's
own trace, not to future context). Attachments referenced by a past turn are not
automatically replayed into a new turn's context — only the current turn's own
attachments are given to a sub-agent, per step 6c of the Sequence.

## Interfaces

- `POST /attachments` — `multipart/form-data` upload; returns an attachment reference.
  Independent of any turn; a turn references it afterward.
- `POST /turns` — submit a message (text, plus zero or more attachment references) into
  a conversation; response is an SSE stream of `progress` events, then token-level
  text for the final answer, then a closing event carrying the turn id and any output
  attachment references (see Sequence).
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

- Error handling within a turn (single tool/LLM failure, partial fan-out failure).
- Verifier invocation UX.
- No-match classifier fallback.
