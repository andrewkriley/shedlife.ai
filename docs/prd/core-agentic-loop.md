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

An independent, post-synthesis agent with no domain bias, invoked manually by the user
against a completed turn. **Open**: the exact UI/interaction for "invoke the verifier"
isn't designed yet — see Open Questions.

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

- **Conversation/session state**: how multi-turn context is maintained across a
  conversation hasn't been designed at all yet — not a gap in this document alone, a
  genuine gap in the design so far.
- **Error handling within a turn**: what happens when one sub-agent's tool call fails,
  an LLM API call errors, or one sub-agent in a multi-match fan-out fails while others
  succeed — not yet designed.
- **Verifier invocation UX**: the mechanism by which a user "manually invokes" the
  verifier against a turn isn't specified.
- **Streaming**: does the chat UI stream a response as it's generated, or wait for full
  turn completion (including synthesis) before showing anything — not yet decided, and
  it materially affects the UI and the API shape between frontend and backend.
- **No-match fallback**: what happens when the classifier finds zero matching
  sub-agents for a message — not yet decided (a catch-all general sub-agent, an
  explicit "I don't know how to help with that," something else).
