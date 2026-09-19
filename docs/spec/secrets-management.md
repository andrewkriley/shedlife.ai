# Secrets Management — SPEC

Status: draft, technical design for
[`../prd/secrets-management.md`](../prd/secrets-management.md). References
[`../architecture.md`](../architecture.md) ("Secrets"), the
[Bootstrap SPEC](./bootstrap.md) (local secret-zero), and the
[Core Agentic Loop SPEC](./core-agentic-loop.md) (the error-handling pattern reused
here rather than duplicated). Infisical-as-platform is Deploy-era.

## Actors / components

- **Secrets client** — a single module every other subsystem calls through; owns the
  cache, the TTL, and the reference-resolution logic. Not reimplemented per subsystem.
- **Local store (bootstrap profile)** — files or rows on the LXC, implementing
  `local://`. This *is* secret-zero for Phase 1.
- **Secrets backend (Infisical)** — after Deploy; external to The Shed's own
  code. Not required to start the bootstrap profile.
- **Kubernetes Secret** — after Deploy, the likely home of the Infisical
  machine identity. Not a Phase 1 artifact.

## Reference format

Bootstrap profile:

```
local://<path...>/<secret_name>
```

Example: `local://providers/llm/api_key`.

After Deploy (scheme reserved now so callers do not invent a third):

```
infisical://<project>/<path...>/<secret_name>
```

Example: `infisical://the-shed/services/unifi-mcp/bearer_token`. GPU
management's LiteLLM/Hugging Face tokens and later seeded platform tokens
use this scheme once that backend exists. The client accepts both; a
profile that has no Infisical must fail `infisical://` fetches the same way
any other missing secret fails.

## Sequence (fetch, happy path)

1. Calling code asks the secrets client for a reference (e.g.
   `local://providers/llm/api_key`, or later
   `infisical://the-shed/providers/anthropic/api_key`).
2. Client checks its in-memory cache. Hit, not expired: return immediately, no
   backend call.
3. Miss or expired:
   - `local://` — read from the LXC store, cache, return.
   - `infisical://` — authenticate using the machine identity (from the
     Kubernetes Secret, read once at process start), fetch, cache with a TTL,
     return. A bootstrap-profile process has no Infisical: this is a miss
     and fails like any other missing secret.
4. **Startup-required secrets** (database connection, and anything else needed before
   the app can serve a single request) are fetched during application boot, not
   lazily on first use — a failure here stops startup with a clear error, per the PRD.
   The bootstrap profile's startup-required secret is the LLM API key after
   setup; before setup, `/setup` is the only live route.
5. **Call-scoped secrets** (a sub-agent's provider key, GPU management's tokens) are
   fetched lazily, at the point of use. A fetch failure here is handled exactly like
   any other transient call failure in the Core Agentic Loop SPEC (retry with
   backoff, then a graceful degraded result) — this subsystem does not define its own
   separate retry/failure behavior.

## Data

The client and cache are not a registry. Durable state:

- Bootstrap: the local store on the LXC (implementation detail: files or
  encrypted rows — not the product repo).
- After Deploy: the Kubernetes Secret holding the Infisical machine
  identity, plus Infisical itself.

## Interfaces

- Internal client interface only (e.g. `secrets.get("local://...")` or
  `secrets.get("infisical://...")`) — no REST endpoint; nothing outside the
  app's own backend process calls this directly. The setup gate writes
  through an internal setter on the local backend, not a public secrets API.

## Security model

- Local-store values never appear in logs, traces, issues, or the
  foundations YAML (references only).
- After Deploy: the machine identity is read once from its mounted
  Kubernetes Secret at process start; never written to disk, logs, or any
  cache that outlives the process.
- Cached secret values live in memory only, for the TTL's duration — not
  persisted, not shared across processes/replicas (each replica maintains
  its own cache; a rotated secret is picked up independently by each within
  its own TTL window, not synchronized).
- One machine identity, scoped to the dedicated project, read-only — per the
  PRD's Scope section — once Infisical exists. The bootstrap local store is
  the equivalent of that single identity for Phase 1.

## Open items

Encryption-at-rest for the LXC local store — desirable, not a Phase 1
blocker. Infisical runtime home — Deploy grill.
