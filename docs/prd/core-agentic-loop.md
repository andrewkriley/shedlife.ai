# Core Agentic Loop — PRD

Status: draft. See [`../spec/core-agentic-loop.md`](../spec/core-agentic-loop.md) for
the technical design this PRD drives, and [`../architecture.md`](../architecture.md)
for the cross-cutting patterns (macro routing, sub-agent registry, fan-out/fan-in,
verifier, classification strategy, secrets, testing discipline) this document turns
into a concrete build.

## Problem

A message needs to reach the right capability (or capabilities), get answered, and
produce one coherent response — extensibly, so a new capability is a registry
addition, not a change to shared routing code; observably, so a cross-domain answer
can be debugged after the fact; and testably, so the orchestration logic itself has
real test coverage rather than being validated only by trying it.

## Goals

- One conversational entry point handles Assist, Build, and Run uniformly — the user
  never has to know or care which macro category their question falls into.
- A new sub-agent is addable without touching the classifier or the orchestration
  engine.
- A question that spans more than one macro category gets one synthesized answer, not
  several disconnected per-domain answers.
- Every turn is traced end-to-end (Galileo), matching the span hierarchy in
  `architecture.md`.
- All deterministic orchestration code (classifier dispatch, registry lookups, the
  fan-out/fan-in engine, provider resolution) is built test-first; LLM-facing behavior
  is validated through tracing/eval, not unit tests, per the testing-discipline split
  already established.
- Built so that later upgrades — parallel sub-agent execution, an auto-triggered
  verifier, a different classification strategy — are config/strategy changes, not
  rearchitecting.

## Non-goals (this phase)

- Parallel sub-agent execution — sequential only; the engine is async-friendly so this
  is a later upgrade, not a rewrite.
- Automatic verifier triggering — manual/user-invoked only this phase.
- Heuristic or hybrid classification strategies — LLM-based only this phase, behind the
  swappable interface.
- A broad sub-agent catalog — one real, working capability per macro category this
  phase (see Success criteria), everything else stubbed or absent.
- Per-user model-assignment configuration — global/admin-level only, until multi-user
  is real.

## Users

- Primary: the single real operator this phase, via the chat UI.
- Data model is multi-user-ready (per `architecture.md`) even though only one user
  exists today.

## Success criteria

- A message sent in the chat UI that touches more than one macro category fans out to
  the correct sub-agents and returns one synthesized answer.
- Three real, working sub-agents exist: `run.network` (via the `unifi-mcp` MCP
  server), `assist` (general web search/fetch), and `build` (fetches a credential from
  the secrets backend, makes one live call against an external dev-tooling API) — not
  stubs.
- Every turn produces a complete trace: classification, each matched sub-agent's own
  span, and synthesis when more than one sub-agent matched.
- The orchestration engine (classifier dispatch, registry lookup, fan-out/fan-in,
  provider resolution) has test coverage from its first commit, with LLM calls mocked.
- A user can manually invoke the independent verifier against a turn's result.

## Requirements

### Turn lifecycle

A message becomes: classify → dispatch to matched sub-agent(s) → each sub-agent runs
its own tool-calling loop → collect results → synthesize (skipped if exactly one
sub-agent matched) → respond. Each stage is its own traced span, matching the
`supervisor → classify → [sub-agent, ...] → synthesis?` shape in `architecture.md`.

### Conversation / session state

- A user has multiple **conversations** (like a chat app's thread list) — not one
  continuous stream, and not split by macro category. A single conversation can touch
  Assist, Build, and Run across its turns, and within one turn via fan-out — the user
  never has to know or choose which macro category they're in, matching this
  document's own top-line goal.
- A conversation has many **turns**; a turn is exactly the lifecycle above. Each turn
  links to its own Galileo trace; each conversation links to one Galileo session,
  grouping its turns' traces together, same pattern as the `cl-ai-builders` reference.
- **Context passed forward** to the classifier and each dispatched sub-agent is only
  past turns' **(user message, final response) pairs** — not their internal tool-call
  detail, which already lives in that turn's own trace for debugging, not for
  context-replay.
- **Context window for this phase**: a simple, **tunable recency cap** — replay the
  last N turns verbatim, drop anything older; N is a configurable default, not a fixed
  number baked into the design. Rolling summarization (compress old turns instead of
  dropping them) is the natural next step once conversations get long enough for
  dropped context to matter — documented roadmap, not built now.

### Streaming

Turns stream over Server-Sent Events, not WebSocket — a turn is one-directional after
the initial request (the server pushes, the client doesn't need to talk back mid-turn;
cancellation is a separate plain request, not a reason for a duplex channel), and SSE
avoids real infrastructure cost that would otherwise apply: since The Shed deploys as a
Kubernetes workload via Flux (potentially multiple replicas), WebSocket would need
either sticky sessions or a pub/sub backplane for a client to keep receiving pushes
regardless of which replica handles a given moment; SSE, being plain HTTP, needs
neither. SSE also reconnects automatically (built into the browser's `EventSource`),
where WebSocket reconnection has to be hand-rolled.

The stream carries two kinds of events: **progress** (classify started/done, each
sub-agent started/done, synthesis started) so the UI shows what's happening rather than
a bare spinner through a turn that can genuinely take some seconds; and **token-level
text** for the one call that actually produces the user-facing answer (the single
sub-agent's response, or the synthesis call's output when more than one matched) — not
every internal call, since most of them (classification, individual tool calls) don't
produce user-facing text worth streaming token-by-token.

### Attachments

Binary data (image upload, and sub-agent-generated output like a diagram or
screenshot) is handled **out-of-band from the turn stream**, the same way most chat
products handle it — not a reason to reconsider SSE:

- **Upload** (user attaches an image to a message): a conventional
  `multipart/form-data` REST upload, separate from the SSE connection, returning an
  attachment reference the client includes when it submits the turn.
- **Output** (a sub-agent generates an image/diagram): the sub-agent stores it and the
  turn's response references it; the SSE event carries a reference/URL, not inlined
  bytes — the browser fetches the actual file over a normal `GET`.
- **Storage**: MinIO (self-hosted, S3-compatible) as another platform-layer,
  Flux-managed workload — consistent with how the database and cache are already
  deployed, not a new deployment pattern.
- Scope includes both **user-uploaded** and **sub-agent-generated** attachments from
  the start, not just user uploads.

### Sub-agent registry

Each entry declares: a unique id (`<macro>.<name>`), its macro category, a one-line
description (what the classifier reads to route to it), a system prompt, a scoped tool
set, a default provider/model, and per-tool `has_side_effects` metadata (feeds the
verifier's future auto-trigger hook). Registering a new sub-agent is adding one entry
— no classifier or engine code changes.

### Classification

Two-tier (macro, then sub-agent), LLM-based this phase, using a cheap/fast model and a
system prompt built dynamically from the registry's own descriptions — a new
sub-agent's description is sufficient for it to be routable, no rule-writing. Built
behind a swappable strategy interface (see `architecture.md`); heuristic and hybrid
remain future options, not built now.

### Fan-out / fan-in

Cross-macro-category fan-out is allowed — one message can dispatch to sub-agents in
more than one macro category at once. Execution is sequential this phase. Synthesis
runs only when more than one sub-agent matched; a single match returns that sub-agent's
own answer directly, no extra call.

### Verifier

An independent, post-synthesis agent with no domain bias, invoked manually by the
user against a completed turn via a "Verify" action attached to that turn in the chat
UI (same pattern as a regenerate/feedback control in most chat products) — not a
separate page or flow. Its result displays inline, expandable, under that turn.

### Loop prevention and side-effect approval

Per `architecture.md`'s cross-cutting requirement: every sub-agent's tool-calling loop
has a max-round cap and a repeated-call guard, extended with two cheap checks built
this phase — canonicalized comparison (catches cosmetically-different-but-identical
calls) and unproductive-result tracking (catches a model that varies its query but
still isn't making progress). Embedding-based similarity and LLM-judged stuckness
remain deliberately deferred — real cost/complexity for a problem the two cheap
checks may already cover. Separately, any tool call flagged `has_side_effects: true`
pauses that sub-agent's loop and requires explicit user approval before executing — a
pre-execution gate, distinct from the post-hoc verifier above. `has_side_effects` is
an enforcement point from this phase, not deferred metadata.

### Error handling within a turn

- A single tool call failing feeds back into that sub-agent's own loop as an
  error-flagged tool result — the model decides how to react, not an exception that
  aborts anything.
- The LLM API call itself failing gets a small retry-with-backoff; if still failing,
  the sub-agent returns a graceful degraded result (`status_code: 1`), reusing the same
  pattern as the turn-limit/repeated-call-guard messages, not a new mechanism.
- One sub-agent failing in a multi-match fan-out: synthesis still runs on whatever
  succeeded, explicitly told which sub-agent(s) failed and why, so the combined answer
  can honestly acknowledge the gap rather than omit it or crash the whole turn.
- Total failure (the only match failed, or every sub-agent in a multi-match failed): a
  dedicated failure signal, not a dropped connection — the turn is still recorded with
  its failed status so conversation history and traces stay consistent.

### No-match fallback

A message the classifier can't route to anything specific falls back to the `assist`
sub-agent (general web search/fetch) rather than a canned "I don't know how to help" —
mirrors the `cl-ai-builders` reference pattern directly (`categories or ["general"]`:
general is the explicit fallback, not a failure state), and gives a genuine attempt at
an answer instead of a dead end.

### Provider/model resolution

Each sub-agent (and the classifier) has a registry-declared default provider/model.
An operator-facing settings surface allows overriding this per sub-agent — select
one/some/all via checkboxes, bulk-assign a provider/model — listing live providers and
models, not a hardcoded list.

### The three real sub-agents this phase

- **`run.network`** — real tools via the existing `unifi-mcp` MCP server (already a
  standing network service). Its `preview_*`/`confirm_*` tool pairing maps directly to
  `has_side_effects: true` for `confirm_*` tools.
- **`assist`** — general web search/fetch as a Q&A capability.
- **`build`** — fetches a credential from the secrets backend via machine identity,
  then makes one real authenticated call against an external dev-tooling API (the
  concrete smoke test for the whole secrets pipeline, not just this sub-agent).

## Open questions

None remaining from this design pass.
