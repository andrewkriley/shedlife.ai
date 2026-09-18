# GPU / Compute Management — SPEC

Status: draft, technical design for
[`../prd/gpu-compute-management.md`](../prd/gpu-compute-management.md). References
[`../architecture.md`](../architecture.md), [`../stack.md`](../stack.md), and the
[Core Agentic Loop SPEC](./core-agentic-loop.md) (provider resolution, the SSE
progress-event pattern this subsystem reuses).

## Actors / components

- **Operator** — via the management UI or the `run.gpu` sub-agent.
- **Host registry** (Postgres) — one row per compute host.
- **Discovery service** — queries a host's GPU inventory, local or over SSH.
- **Deployment manager** — starts/stops a subprocess-managed model-serving instance on
  a host; submits long-running work (downloads, remote deploys) to the job queue.
- **Job queue** (Redis-backed, per `stack.md`) — the same queue used elsewhere in the
  stack, not a dedicated one for this subsystem.
- **Instance registry** (Postgres) — one row per deployed model instance, including its
  in-use reference count.
- **`run.gpu` sub-agent** — a registry entry like any other (per Core Agentic Loop),
  whose tools call the same deployment manager the UI calls.

## Sequence (happy path: register host, deploy one model)

1. Operator registers a host (local, or SSH-reachable remote) via the management UI or
   the `run.gpu` sub-agent — same underlying call either way.
2. Discovery runs against that host, populating its GPU inventory in the registry.
   Re-run on demand, not assumed to stay accurate indefinitely.
3. Operator selects a model to download. This is submitted as a job (Redis queue);
   progress streams the same way a turn's progress does (SSE), not a bespoke polling
   mechanism for this one subsystem.
4. Once downloaded, operator requests deployment onto a specific GPU on a specific
   host. Also a job: starts the subprocess-managed instance, assigns it a port.
5. **Validation**: once the process is up, a real request against its own API confirms
   it's actually serving before the instance is marked usable — not just "the process
   didn't crash."
6. The now-validated instance registers itself with LiteLLM via LiteLLM's own dynamic
   Model Management API (register a model alias against this instance's host:port) —
   immediately routable, no LiteLLM restart, no disruption to other models already
   routing through the same gateway.
7. From this point, every sub-agent call that resolves to this instance increments its
   reference count on start and decrements on finish — the same code path as the Core
   Agentic Loop's provider-resolution step, not a second bookkeeping mechanism.
8. An operator-initiated unload checks the reference count first: zero, proceeds
   (deregistering from LiteLLM the same way it registered, then stopping the
   subprocess); non-zero, a visible warning in the UI rather than silently blocking or
   silently allowing.

## Data

### Hosts (Postgres)

| Field | Notes |
|---|---|
| `id` | Registry entry id |
| `connection` | `local`, or SSH details for remote (host, user, key reference — the same dedicated-key credential model used elsewhere, not a new one) |
| `gpus` | Discovered inventory (model, memory, driver/CUDA version); refreshed on demand |
| `provenance` | `manual` \| `discovered` \| `provisioned` — same field as every other registry entry in `architecture.md` |

### Instances (Postgres)

| Field | Notes |
|---|---|
| `id` | |
| `host_id` / `gpu_id` | Which host and GPU this instance runs on |
| `model` | What's loaded |
| `port` | Assigned serving port |
| `status` | `downloading` \| `deploying` \| `validating` \| `running` \| `stopped` \| `failed` |
| `in_use_count` | Reference count; gates manual unload (see Sequence step 8) |
| `litellm_model_alias` | The name it's registered under in LiteLLM once validated; null until step 6 of the Sequence completes |

## Interfaces

- REST endpoints for host registration, discovery trigger, model list/download,
  instance deploy/stop/status — mirrored by the `run.gpu` sub-agent's tool set, not a
  separate API surface for conversational use.
- Long-running operations (download, deploy) return a job reference; progress streams
  over SSE, consistent with the Core Agentic Loop's transport choice — not a second
  streaming mechanism for this subsystem to maintain.
- LiteLLM's own Model Management API (`/model/new`, `/model/delete`) is called by the
  deployment manager on successful validation and on stop — not exposed directly to
  the operator or the `run.gpu` sub-agent; it's an internal step of deploy/stop, not a
  separate capability.

## Security model

- Remote host access uses the same dedicated-SSH-key credential model established
  elsewhere in this design (Bootstrap's dedicated keypair pattern) — not a second,
  separately-managed credential for the same kind of access.
- In-use tracking is a hard gate on manual unload, not advisory — consistent with the
  `architecture.md` principle that shared-resource teardown requires usage tracking
  before any teardown decision, automated or manual.
- Calling LiteLLM's Model Management API requires its own admin/master key, fetched
  from the secrets backend at call time — same pattern as every other credential in
  this design, not a new mechanism.

## Infrastructure implication

**LiteLLM needs a database configured** so dynamic model registrations (Sequence step
6) survive its own restarts — in-memory-only registrations vanish on restart, silently
un-routing every locally-deployed model. LiteLLM itself is a Fleet-repo **platform
layer** workload (Bootstrap design), not assumed to just exist.

## Open items

Mirrors the PRD's Open Questions:

- Model catalog source (live Hub query, curated list, or both).
