# GPU / Compute Management — PRD

Status: draft. See
[`../spec/gpu-compute-management.md`](../spec/gpu-compute-management.md) for the
technical design this PRD drives, and [`../architecture.md`](../architecture.md) for
the cross-cutting pattern (layered pipeline, provenance, in-use tracking before
automated lifecycle decisions) this document turns into a concrete build. Inspired by
`vllm_manager` (see `decisions.md` history) but built natively into The Shed, not
consumed as an external service.

## Problem

Running models locally needs a real lifecycle — knowing what compute exists, what it
has, what's deployed on it, and whether something using it right now would break if it
were torn down — not just "start a process and hope." Without this, RUN's own compute
management is either entirely manual and undocumented, or automated in a way that can
silently disrupt an in-flight sub-agent call.

## Goals

- A host registry that treats compute (local machine, remote VM, dedicated hardware)
  as data, not a hardcoded target — consistent with the host/service registry pattern
  in `architecture.md`.
- A working, real path from "register a host" to "a validated, running model instance
  on it" for the single-host/single-GPU case.
- **In-use tracking from day one**: no manual or automated teardown of a model that's
  actively serving a sub-agent call, ever.
- Surfaced two ways: conversationally (a `run.gpu` sub-agent) and through a dedicated
  management UI — the same underlying operations, not two separate implementations.
- Built so multi-GPU-per-host and multi-host clustering are later phases of the same
  pipeline shape, not a redesign.

## Non-goals (this phase)

- Multi-GPU-per-host and multi-host (Ray) clustering — roadmap, not built.
- Dynamic auto-load/unload tied to routing decisions — explicitly deferred; an
  in-flight sub-agent call must never be disrupted by an unrelated routing decision
  elsewhere in the system. Manual operator action only, this phase.
- Shared/clustered storage for model files across hosts — out of scope; each host
  manages its own local model storage this phase.

## Users

- Primary: the operator, via the management UI and/or the `run.gpu` sub-agent.

## Success criteria

- An operator can register a host (localhost, or a remote host/VM with GPU
  passthrough), see its GPU discovered automatically, download a model, deploy it as a
  running instance, and have that instance validated (a real smoke-test call, not just
  "the process started") — for exactly one GPU on that host.
- The same flow works identically whether initiated from the management UI or by
  asking the `run.gpu` sub-agent conversationally.
- A loaded model's in-use state is visible in the UI, and a manual unload attempt on an
  in-use model is a visible warning, not a silent race — reference-counted against
  actual sub-agent calls, not a best-effort guess.
- A newly-deployed local instance becomes usable by the rest of the system (sub-agents
  can actually route to it) without a manual config-file edit.

## Requirements

### Host registry

Each host entry: id, connection details (`local` or SSH-reachable remote), discovered
GPU inventory (refreshed on demand, not assumed static), and `provenance` — same field
as every other registry entry in `architecture.md` (`manual` this phase; `discovered`/
`provisioned` apply once the Bootstrap-designed host provisioning exists).

### Discovery

Local: direct GPU query on the host The Shed itself runs on. Remote: over the same
SSH credential model established for host access elsewhere in this design (a
dedicated key, not a shared/reused one) — consistent with not inventing a second
credential mechanism for the same kind of access.

### Deployment

Subprocess-managed model serving on the target host, matching the `vllm_manager`
reference this subsystem is inspired by — not a redesign of that proven mechanism,
just rebuilt natively. Model downloads and remote deployments are genuinely
long-running, so both go through the Redis-backed job queue already in the stack, not
a blocking request — with progress observable the same way a turn's progress is (see
Core Agentic Loop's SSE pattern), not a different mechanism for a different kind of
long-running operation.

### Validation

A real request against the deployed instance's own API (not just "the process is
still running") before it's marked usable.

### Becoming routable (resolves the prior open question)

A validated instance registers itself with LiteLLM via LiteLLM's own dynamic Model
Management API — not a static config file edit (which would need a reload/restart,
risking disruption to other models already routing through the same gateway) and not
a gateway bypass for freshly-deployed instances (which would mean two different code
paths for reaching a local model depending on how it got deployed). Stopping an
instance deregisters it the same way — symmetric, not a one-directional registration
that leaves stale routes behind. The registered model alias matches the name a
sub-agent's registry entry references, so provider resolution (Core Agentic Loop)
finds it the same way regardless of when it was deployed.

This has one real infrastructure implication: **LiteLLM needs a database configured**
so these dynamic registrations survive its own restarts (in-memory-only registrations
vanish on restart) — and LiteLLM itself belongs in the Fleet repo's **platform layer**
(a Flux-managed workload, per the Bootstrap design), not something assumed to just
exist.

### In-use tracking

A reference count per loaded model, incremented when a sub-agent call starts against
it and decremented when it finishes — this is the same moment the Core Agentic Loop's
provider resolution step (see its SPEC) picks a local model for a sub-agent call, so
the two need to be the same code path, not two places that could drift out of sync. A
manual unload attempt while the count is non-zero is a visible warning in the
management UI, not silently blocked and not silently allowed.

### Dual surface

The `run.gpu` sub-agent (list hosts/GPUs, list/download models, deploy/stop an
instance, report status) and the management UI call the same underlying operations —
the sub-agent is not a separate, parallel implementation of host/deployment logic.

### Model catalog

A live query against Hugging Face Hub, not a curated list — matches `vllm_manager`'s
own approach, and avoids maintaining a second, always-stale list of what's actually
available upstream. The operator can supply a Hugging Face API token (fetched from the
secrets backend, same pattern as every other credential in this design, never stored
in plaintext): optional for public, non-gated models — downloads work without it, just
slower/rate-limited — but required for gated repos (Llama and similar, which need both
an accepted license and a token) and generally faster with one.

## Open questions

None remaining from this design pass.
