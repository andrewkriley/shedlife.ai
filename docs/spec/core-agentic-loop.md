# Core Agentic Loop — SPEC

Status: living-harness design. Phase 1 reuses these interfaces as the
bootstrap profile (one agent, classification short-circuit, `Secure`
cookies off). See [`bootstrap.md`](./bootstrap.md).

Technical design for
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
5. **Zero matches**: fall back to the `assist` sub-agent as the sole match, and
   continue at step 6 as if it had been classified normally — no separate code path.
6. **One or more matches**, sequentially (this phase — see PRD non-goals on
   parallelism): for each matched sub-agent — an SSE `progress` event
   (`agent:<id> started`) is emitted, then:
   a. Resolve its provider/model (registry default, or an operator override from the
      settings surface).
   b. Open an `agent` span for this sub-agent.
   c. Seed its tool-calling loop's message list with the same loaded context from step
      2, followed by the current user message (and any attachments, for a sub-agent
      whose model supports image input).
   d. Run its tool-calling loop: call the model with its scoped tools. Safety nets
      apply throughout, per `architecture.md`: a max-turn cap; a repeated-call guard
      comparing canonicalized arguments (trimmed, key-sorted, type-normalized), not
      raw exact match; and tracking of the last K tool results, flagging the loop as
      stuck if they're all effectively unproductive regardless of whether the calls
      varied. If a tool call is flagged `has_side_effects: true`, the loop
      **pauses** and an SSE `approval_required` event is emitted (tool name, arguments,
      sub-agent id); execution resumes only on an explicit approval response over a
      companion endpoint (see Interfaces), or the loop ends if the user declines. An
      executed tool call that fails feeds its error back into the loop as an
      error-flagged tool result — the model decides how to react, not an exception. If
      a tool call produces an attachment (a diagram, a screenshot), it's stored via the
      attachments endpoint and referenced in the sub-agent's result, not inlined.
   e. If the LLM API call itself fails (not a tool failure): retry with backoff, small
      cap; if still failing, this sub-agent's result becomes a graceful degraded
      message with `status_code: 1` — same pattern as the turn-limit/repeated-call
      messages, not a new mechanism.
   f. Close the sub-agent's span with its result and status code. An SSE `progress`
      event (`agent:<id> done`, carrying the status) is emitted.
7. **Exactly one match**: that sub-agent's result is the turn's final answer, streamed
   token-by-token over the same SSE connection as it's produced — no synthesis call. If
   that one sub-agent failed (step 6e), the failure message is the final answer, and an
   SSE `error` event accompanies it.
8. **More than one match**: an SSE `progress` event (`synthesis started`) is emitted;
   the synthesis step combines all matched sub-agents' results (no tools, one LLM
   call) into one answer, streamed token-by-token as produced. Any sub-agent that
   failed is passed into synthesis as an explicit "this failed, here's why" input, not
   silently dropped, so the combined answer can honestly acknowledge the gap. If
   *every* matched sub-agent failed, synthesis is skipped and an SSE `error` event
   carries a turn-level failure instead.
9. A final SSE event carries the completed answer's metadata (any attachment
   references, the turn id) and closes the stream. The turn is recorded regardless of
   outcome (including a fully-failed turn), so conversation history and traces stay
   consistent.
10. The `supervisor` span closes; the trace concludes.
11. *(Optional, user-invoked, any time after step 10, via a "Verify" action in the chat
    UI attached to this turn)*: `POST /turns/{id}/verify`. The verifier reviews the
    final answer against the original message, with no domain-scoped tools of its own,
    and returns an assessment as its own traced span, not folded into the original
    trace; its result is stored (`turn_verifications`) and displayed inline under that
    turn in the UI.

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

### Provider/model overrides (Postgres)

| Table | Key fields |
|---|---|
| `sub_agent_model_overrides` | `sub_agent_id`, `provider`, `model`, `set_by_user_id`, `set_at` — one row per sub-agent currently overridden; absence of a row means "use the registry default." Provider resolution checks this table first, falling back to the registry's `default_provider`/`default_model`. A release that changes the registry default does not delete or rewrite these rows. |

### Conversation / turn (Postgres)

| Table | Key fields |
|---|---|
| `conversations` | `id`, `user_id` (owner, per the multi-user-ready data model), `galileo_session_id`, `created_at` |
| `turns` | `id`, `conversation_id`, `user_message`, `final_response`, `galileo_trace_id`, `created_at` |
| `turn_sub_agent_results` | `turn_id`, `sub_agent_id`, `result`, `status_code` — one row per sub-agent matched in that turn, for the verifier and for debugging; **not** replayed as future context (only `turns.final_response` is) |
| `attachments` | `id`, `owner_user_id`, `source` (`upload` \| `generated`), `content_type`, `size_bytes`, `storage_key` (MinIO object key), `created_at` |
| `turn_attachments` | `turn_id`, `attachment_id`, `role` (`input` \| `output`) — join table linking attachments to the turn they were submitted with or produced by |
| `turn_verifications` | `id`, `turn_id`, `result`, `galileo_trace_id`, `invoked_by_user_id`, `invoked_at` — one row per manual verifier invocation |

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
  a conversation; response is an SSE stream: `progress` events, an `approval_required`
  event if a side-effect tool call is pending, token-level text for the final answer
  (or an `error` event on failure), then a closing event carrying the turn id and any
  output attachment references (see Sequence). The client parses `fetch()` bytes
  (Starlette emits `\r\n`); normalize to `\n` before splitting on blank lines.
  When the stream ends, parse any leftover buffer — a missing trailing blank
  line otherwise drops the last `error` or `done` and the UI shows nothing.
  Vendor failures surface the provider `error.message`, not the SDK dump.
- `POST /turns/{id}/approvals` — respond (approve/decline) to a pending
  `approval_required` event for that turn; resumes or ends the paused tool loop.
- `POST /turns/{id}/verify` — manually invoke the verifier against a completed turn;
  returns its assessment (also stored in `turn_verifications`).
- Settings surface (REST): list sub-agents; `POST /settings/model-assignments` to
  bulk-assign a provider/model to a selected set of sub-agents (writes/clears rows in
  `sub_agent_model_overrides`). Assigning a provider that is not the live client
  is `400` — save that key first. Chat, the connection header, classify,
  synthesize, and verify all resolve the live vendor + matching override (or
  that vendor's default); a Claude override is never sent to OpenAI.
  `GET /settings/models` lists live options — a real
  call to each cloud provider's own models-list API, plus whatever's currently
  registered in LiteLLM for local models (the same registrations GPU/Compute
  Management creates — this endpoint reads them, it doesn't maintain a second list).
  `GET`/`POST /settings/galileo` exist on the living harness for later
  phases; Bootstrap does not collect or show Galileo.

## Security model

- **Tool scoping is strictly enforced**: a sub-agent's executor only has access to the
  tools declared in its own registry row — not the full tool catalog, not another
  sub-agent's tools.
- **`has_side_effects` is an enforcement point, not deferred metadata**: a flagged tool
  call cannot execute without an explicit approval response over `POST
  /turns/{id}/approvals` — this is live from this phase, not held for a future
  auto-trigger feature (which remains a separate, not-yet-built concern: the verifier's
  own automatic triggering, per `architecture.md`).
- Secrets are fetched at call time via machine identity, never cached to disk, per the
  secrets pattern in `architecture.md`.

## Open items

None remaining from this design pass. Embedding-based semantic similarity and
LLM-judged stuckness detection remain deliberately deferred roadmap, per
`architecture.md` — not blocking, and not the same as an unresolved open item.
