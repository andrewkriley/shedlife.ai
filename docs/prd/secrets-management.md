# Secrets Management — PRD

Status: draft. See
[`../spec/secrets-management.md`](../spec/secrets-management.md) for the technical
design this PRD drives, and [`../architecture.md`](../architecture.md) ("Secrets")
for the cross-cutting pattern this document turns into a concrete build.

## Problem

Every subsystem designed so far — sub-agent tool calls, GPU management's Hugging Face
and LiteLLM credentials, Bootstrap's seeded tokens — assumes secrets are "fetched from
the backend at call time," referenced informally. That assumption has never been
pinned down as an actual contract: what the reference format is, how long a fetched
value is trusted before re-checking it, what happens when the backend is unreachable,
and where the one unavoidable plaintext credential actually lives at runtime.

## Goals

- One formal secret-reference format, used identically everywhere a secret is named
  across every other subsystem's docs.
- Rotation in the secrets backend is picked up by the running app without requiring a
  restart.
- A clear, different failure behavior for "can't get a secret needed at startup" vs.
  "can't get a secret needed for one call" — not the same handling for both.
- The one plaintext credential ("secret zero") has an explicit, concrete home now that
  the deployment target (Kubernetes via Flux) is known — not a vague ".env file"
  left over from before that was decided.

## Non-goals (this phase)

- Per-sub-agent or per-purpose machine identities (finer-grained internal scoping) —
  one machine identity with read access to everything under the dedicated project is
  this phase's default; roadmap if finer scoping is ever needed.
- Secret *writing* from The Shed — this design is read-only consumption, per
  `architecture.md`; nothing in this phase changes that.

## Users

- Every subsystem in this design that names a credential — not a user-facing feature
  in its own right.

## Success criteria

- A secret reference resolves the same way regardless of which subsystem is asking for
  it — GPU management's LiteLLM/Hugging Face credentials, a sub-agent's provider API
  key, Bootstrap's seeded tokens, all through one client, one format.
- Rotating a secret in the backend is reflected in the running app within a bounded,
  short window — no restart required.
- The app fails fast and clearly if a startup-required secret can't be fetched; a
  single sub-agent call's own credential failure degrades only that call, using the
  same error-handling pattern already designed in the Core Agentic Loop, not a new one.

## Requirements

### Reference format

A single URI scheme (see SPEC for the exact grammar) used everywhere a secret is
named — the same format already used informally in Bootstrap's `instance.yaml`
illustration and the Fleet repo pattern, now formalized rather than left as an
example.

### Caching and rotation

Fetched values are cached in memory with a short, tunable TTL — not fetched fresh on
literally every call (unnecessary latency and a hard per-call dependency on the
backend being reachable), and not cached indefinitely until restart (rotation would
never be picked up). Expiry triggers a re-fetch, not a manual refresh action.

### Failure handling

- A secret required at **startup** (the app's own operating credentials — database,
  etc.): the app fails to start, clearly, rather than starting in a partially-broken
  state.
- A secret required for **one call** (a sub-agent's provider credential, GPU
  management's Hugging Face/LiteLLM tokens): that call fails using the same
  retry-with-backoff-then-graceful-degradation pattern already designed for any other
  transient failure in the Core Agentic Loop SPEC — not a separate mechanism invented
  for secrets specifically.

### Secret zero's runtime home

Given the deployment target is Kubernetes via Flux (per the Bootstrap design), the one
unavoidable plaintext credential (the machine identity used to reach the secrets
backend) is a **Kubernetes Secret**, referenced by The Shed's own deployment manifest
in the Fleet repo's `apps/` layer — not a literal `.env` file on a persistent disk.
This supersedes the earlier, pre-Kubernetes-design framing in `architecture.md`.

### Scope

One machine identity, read access to everything under the dedicated project — not
scoped further per sub-agent or per purpose this phase. Finer-grained scoping is a
reasonable later hardening step, not validated as necessary yet.

## Open questions

None remaining from this design pass.
