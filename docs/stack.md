# The Shed — Reference Stack

The specific technologies chosen to implement the pattern described in
[`architecture.md`](./architecture.md). These are opinionated defaults for this
deployment, not part of the pattern itself — each one is swappable without changing the
architecture around it. Nothing here is specific to any particular environment; no
URLs, project names, or credentials belong in this file.

Phase-scoping (what exists in Bootstrap vs. later) is in [`mvp.md`](./mvp.md).

## Backend

**Python + FastAPI.** Native SDKs for the major LLM providers and for MCP are
first-class in Python; the wider ecosystem this kind of harness tends to grow into
(GPU tooling, orchestration/automation libraries, infra SDKs) is Python-heavy; mature
test tooling (`pytest`, `pytest-asyncio`, HTTP/LLM call mocking libraries) supports the
test-first discipline the architecture calls for.

## Frontend

**React + TypeScript + Vite**, served as a SPA; the backend is a pure JSON API
(SSE for turns), no server-side rendering. Chosen over a minimal/vanilla frontend
because: the actual UI surface (chat, a foundations/review panel, a settings/config
panel, a resource-management panel, future role-differentiated views) is real
application complexity, not a single page; a component framework is what turns a
design-token file into an actual reusable component system; and the testing
ecosystem around component frameworks (component unit tests, testing-library-style
assertions) is what makes the frontend testable at all under a test-first
discipline — vanilla DOM manipulation is not.

### Visual tokens

The UI consumes the **`therileys-team`** token set from
[andrewkriley/design-system](https://github.com/andrewkriley/design-system)
(`design-system/tokens/therileys-team.json`). This is a token-only pattern, not a
brand-voice profile — no manifest/voice to apply. It is **self-contained**: it
does not merge with `design-system/tokens/shared.json`.

- Resolve `{a.b.c}` values as references to another token's dot-path — see
  `design-system/tooling/CONSUME.md`, or `design-system/demo/app.js`'s
  `flattenTokens` / `resolveOne`.
- Accent colors are mid-bright. Filled accent surfaces use `color.bg.canvas`
  text, not white — see `withPatternColorAliases` in that demo `app.js`.
- Dark only (`meta.mode: "Dark"`). No light variant.

`brand/tokens.json` in this repo is the vendored copy of that set. The running
CSS must be derived from it; a light-mode fallback is a bug.

## Persistence

**PostgreSQL**, with an async ORM and a migration tool. The data model is inherently
relational (users, sessions, registry entries, sub-agent config, foundations,
issues), and Postgres's ecosystem for testing (transactional isolation, mature tooling)
supports the test-first discipline. A vector-search extension is enabled from day one,
unused until a retrieval/memory feature needs it — enabling it costs nothing now;
adding it to an existing schema later is real migration work.

In the **bootstrap profile** this Postgres (and the Redis below) run *inside*
the bootstrap LXC. That is still "local storage." A later Deploy grill decides
whether a platform Postgres replaces it.

## Background jobs

**A Redis-backed job queue.** Some operations (model downloads, remote deployments,
anything that spans more than one request/response cycle) need durable, queryable,
progress-reporting state that survives a process restart — an in-process task isn't
enough. Redis-backed queues (Celery, RQ, Arq, etc. — the specific library is an
implementation detail, not fixed here) are the standard way to get that without
building bespoke job infrastructure.

## Model providers

- **Anthropic, OpenAI, and Gemini**, called via their own native SDKs — full
  feature fidelity (prompt caching, native tool-use semantics), rather than
  flattened through a compatibility layer. A Claude *subscription* (or any
  browser-login / Claude Code credential) is not a supported auth path; an
  API key is required. OpenAI reasoning models do not share one
  `reasoning_effort` value: `gpt-5` / `gpt-5-mini` accept `minimal` (not
  `none`); `gpt-5.4*` accepts `none`; o-series wants `low` / `medium` /
  `high`. Sending the wrong one is a 400 with no chat reply.
- Galileo is the tracing/eval layer (see Observability). Its OpenAI wrapper
  is sync-only and is **not** placed in front of the async/streaming path;
  Anthropic and Gemini are native + manual spans, matching Galileo's own
  documented pattern for those providers.
- **A gateway (e.g. LiteLLM) in front of local model runtimes only** (e.g. vLLM,
  Ollama) — not in front of the cloud providers above. Local runtimes typically speak
  an OpenAI-compatible wire format already, so a local model becomes "one more provider
  with a different endpoint," reusing the same code path as the cloud OpenAI-compatible
  case rather than a separate integration. A newly-deployed local instance registers
  itself with the gateway via its own dynamic model-management API rather than a
  static config file — see the GPU/Compute Management SPEC. This requires the gateway
  to have a database configured so those registrations survive its own restarts.
  LiteLLM itself is a Deploy/Build concern, not a Bootstrap one.

## Secrets backend

The secrets **client interface** is one module. The backend behind it is
phase-dependent:

- **Bootstrap profile**: a local store on the LXC (`local://...` references).
  This *is* secret-zero.
- **After Deploy**: an external secrets manager (e.g. Infisical, Vault,
  cloud-provider secret stores), consumed read-only via machine identity, per
  the secrets pattern in `architecture.md`. The specific product is a
  swappable implementation detail behind that pattern.

## Observability

Agent/tool tracing via a dedicated LLM observability platform (Galileo),
structured around the same span hierarchy the architecture describes (a top-level span
per turn, containing classification and each matched sub-agent's own span, grouped into
sessions per conversation). Optional in Bootstrap: missing Galileo credentials
keep a no-op tracer; a turn must never fail because tracing is down. This is
observability, not a testing mechanism — see the testing-discipline section of
`architecture.md`.

Infra metrics (Grafana, Prometheus, later Splunk) are a different concern and
are not in this stack until their phase grill.
