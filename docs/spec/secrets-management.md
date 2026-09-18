# Secrets Management — SPEC

Status: draft, technical design for
[`../prd/secrets-management.md`](../prd/secrets-management.md). References
[`../architecture.md`](../architecture.md) ("Secrets"), the
[Bootstrap SPEC](./bootstrap.md) (secret-zero, seeding), and the
[Core Agentic Loop SPEC](./core-agentic-loop.md) (the error-handling pattern reused
here rather than duplicated).

## Actors / components

- **Secrets backend (Infisical)** — external to The Shed's own code; a
  platform-layer, Flux-managed workload per the Bootstrap design.
- **Secrets client** — a single module every other subsystem calls through; owns the
  cache, the TTL, and the reference-resolution logic. Not reimplemented per subsystem.
- **Kubernetes Secret** — holds the one plaintext credential (machine identity) the
  client uses to authenticate to Infisical; injected into The Shed's container by its
  own deployment manifest.

## Reference format

```
infisical://<project>/<path...>/<secret_name>
```

Example (already used informally in the Bootstrap PRD's `instance.yaml`
illustration): `infisical://the-shed/services/unifi-mcp/bearer_token`. Every other
subsystem's docs that name a secret use this same format — GPU management's LiteLLM
admin key and Hugging Face token, a sub-agent's provider API key, Bootstrap's seeded
Fleet-repo-host/DNS tokens.

## Sequence (fetch, happy path)

1. Calling code asks the secrets client for a reference (e.g.
   `infisical://the-shed/providers/anthropic/api_key`).
2. Client checks its in-memory cache. Hit, not expired: return immediately, no network
   call.
3. Miss or expired: authenticate to Infisical using the machine identity credential
   (from the Kubernetes Secret, read once at process start, never re-read from disk
   after), fetch the value, cache it with a TTL, return it.
4. **Startup-required secrets** (database connection, and anything else needed before
   the app can serve a single request) are fetched during application boot, not
   lazily on first use — a failure here stops startup with a clear error, per the PRD.
5. **Call-scoped secrets** (a sub-agent's provider key, GPU management's tokens) are
   fetched lazily, at the point of use. A fetch failure here is handled exactly like
   any other transient call failure in the Core Agentic Loop SPEC (retry with
   backoff, then a graceful degraded result) — this subsystem does not define its own
   separate retry/failure behavior.

## Data

No new database tables — this subsystem is a client library and a cache, not a
registry. The only durable state is the Kubernetes Secret itself (outside Postgres,
managed by the Fleet repo's manifests).

## Interfaces

- Internal client interface only (e.g. `secrets.get("infisical://...")`) — no REST
  endpoint; nothing outside the app's own backend process calls this directly.

## Security model

- The machine identity credential is read once from its mounted Kubernetes Secret at
  process start; never written to disk, logs, or any cache that outlives the process.
- Cached secret values live in memory only, for the TTL's duration — not persisted,
  not shared across processes/replicas (each replica maintains its own cache; a
  rotated secret is picked up independently by each within its own TTL window, not
  synchronized).
- One machine identity, scoped to the dedicated project, read-only — per the PRD's
  Scope section; no per-subsystem credentials to manage separately.

## Open items

None remaining from this design pass.
