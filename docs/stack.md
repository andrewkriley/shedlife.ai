# The Shed — Reference Stack

The specific technologies chosen to implement the pattern described in
[`architecture.md`](./architecture.md). These are opinionated defaults for this
deployment, not part of the pattern itself — each one is swappable without changing the
architecture around it. Nothing here is specific to any particular environment; no
URLs, project names, or credentials belong in this file.

## Backend

**Python + FastAPI.** Native SDKs for the major LLM providers and for MCP are
first-class in Python; the wider ecosystem this kind of harness tends to grow into
(GPU tooling, orchestration/automation libraries, infra SDKs) is Python-heavy; mature
test tooling (`pytest`, `pytest-asyncio`, HTTP/LLM call mocking libraries) supports the
test-first discipline the architecture calls for.

## Frontend

**React + TypeScript + Vite**, served as a SPA; the backend is a pure JSON/WebSocket
API, no server-side rendering. Chosen over a minimal/vanilla frontend because: the
actual UI surface (chat, a settings/config panel, a resource-management panel, future
role-differentiated views) is real application complexity, not a single page; a
component framework is what turns a design-token file into an actual reusable
component system; and the testing ecosystem around component frameworks (component
unit tests, testing-library-style assertions) is what makes the frontend testable at
all under a test-first discipline — vanilla DOM manipulation is not.

## Persistence

**PostgreSQL**, with an async ORM and a migration tool. The data model is inherently
relational (users, sessions, registry entries, sub-agent config), and Postgres's
ecosystem for testing (transactional isolation, mature tooling) supports the test-first
discipline. A vector-search extension is enabled from day one, unused until a
retrieval/memory feature needs it — enabling it costs nothing now; adding it to an
existing schema later is real migration work.

## Background jobs

**A Redis-backed job queue.** Some operations (model downloads, remote deployments,
anything that spans more than one request/response cycle) need durable, queryable,
progress-reporting state that survives a process restart — an in-process task isn't
enough. Redis-backed queues (Celery, RQ, Arq, etc. — the specific library is an
implementation detail, not fixed here) are the standard way to get that without
building bespoke job infrastructure.

## Model providers

- **Major cloud providers** (e.g. Anthropic, OpenAI) called via their own native SDKs
  — full feature fidelity (prompt caching, native tool-use semantics), rather than
  flattened through a compatibility layer.
- **A gateway (e.g. LiteLLM) in front of local model runtimes only** (e.g. vLLM,
  Ollama) — not in front of the cloud providers above. Local runtimes typically speak
  an OpenAI-compatible wire format already, so a local model becomes "one more provider
  with a different endpoint," reusing the same code path as the cloud OpenAI-compatible
  case rather than a separate integration. A newly-deployed local instance registers
  itself with the gateway via its own dynamic model-management API rather than a
  static config file — see the GPU/Compute Management SPEC. This requires the gateway
  to have a database configured so those registrations survive its own restarts.

## Secrets backend

An external secrets manager (e.g. Infisical, Vault, cloud-provider secret stores),
consumed read-only via machine identity, per the secrets pattern in `architecture.md`.
The specific product is a swappable implementation detail behind that pattern.

## Observability

Agent/tool tracing via a dedicated LLM observability platform (e.g. Galileo, Langfuse),
structured around the same span hierarchy the architecture describes (a top-level span
per turn, containing classification and each matched sub-agent's own span, grouped into
sessions per conversation). This is observability, not a testing mechanism — see the
testing-discipline section of `architecture.md`.
