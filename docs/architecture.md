# The Shed — Architecture

This document describes the **portable pattern**: the parts of the design that don't
depend on any particular environment, provider, or tool. It contains no URLs, tokens,
credentials, or references to any specific deployment. Anyone building a similar
agentic harness could apply this document as-is.

For the specific technologies chosen to implement this pattern in this deployment, see
[`stack.md`](./stack.md). For what is in the current MVP versus later phases, see
[`mvp.md`](./mvp.md). Design decisions that produced this shape are recorded in
[`grill/`](./grill/).

---

## What this is

A web-based, agentic-first AI harness built around fan-out/fan-in orchestration of
agents and sub-agents, capable of using a mix of AI model providers (cloud and local).

The Shed has three **jobs**: **Assist** (the everyday personal-assistant work of
running a life), **Build** (new projects, new features, fixes — for The Shed itself
or anything else), and **Run** (operating the infrastructure underneath all of it —
hosting, network, cloud, home tech stack). One conversational interface, a growable
registry of domain-specific sub-agents, fanning out to whichever of them a message
actually needs and fanning back in to one answer.

## Lifecycle phases are not jobs

A tenant comes up, and is then used, in four **phases**:

1. **Bootstrap** — solve the chicken-and-egg: a thin installer starts a control
   plane that can talk to a human and remember facts. It does not provision the
   platform.
2. **Deploy** — stand up the foundational platforms and services from those facts.
3. **Build** — add the tools and toys the tenant actually wants.
4. **Run** — operate what was stood up (AI Ops, patrols).

Assist / Build / Run as **jobs** are a classification dimension inside the running
harness (see below). Bootstrap / Deploy / Build / Run as **phases** are chapters
of a tenant's life. The names collide on purpose with how the product is spoken
about; they are not the same thing. In writing, say "the Bootstrap phase" or
"the Build job" whenever either reading is possible.

The Bootstrap assistant is a constrained Assist-job agent. Later phases add
assistants (and playbooks) under the job that matches the work. Phase 3 uses the
Build job; Phase 4 uses the Run job.

## Macro categories are a routing dimension, not agents

The top-level categories a message can be routed to (this instance defines three:
**Assist**, **Build**, **Run**) are a **classification dimension** — "what kind of work
is this" — not agents in their own right. There is no LLM call and no observability
span at this level. The number and naming of macro categories is a deployment choice;
the pattern generalizes to any set.

The only real agents — LLM-backed, with their own system prompt, their own scoped
tools, and their own trace span — are **domain-specific sub-agents**, each registered
under exactly one macro category (e.g. a networking sub-agent under Run, a
bug-fixing sub-agent under Build, a calendar sub-agent under Assist).

A **profile** is a permitted subset of that registry plus the secret-zero and
persistence story that profile is allowed to assume. The bootstrap profile is
the first one: one intake agent, local secret-zero, no platform services
required. Adding Deploy does not invent a second harness; it grows the registry
and swaps secret-zero for a real secrets backend.

When the registry contains exactly one agent, classification is a short-circuit,
not a model call.

## Sub-agent registry

Sub-agents are added via a registry, not by editing a central classifier. A new domain
registers itself — a name, a one-line description, a macro category, a system prompt,
a scoped tool set, a default model — without the classifier or any other sub-agent
needing to change. This is what keeps the system's surface area growable: adding a new
capability is additive, not a modification to shared routing logic.

## Classification

Routing a message to the right sub-agent(s) is two-tier: first the macro category,
then the specific sub-agent(s) within it. This is implemented behind a **swappable
classification strategy interface**, so the actual mechanism can be changed without
touching the orchestration engine around it. Three mechanisms are worth naming:

- **Heuristic** (keyword/rule-based): fast and free, but the ruleset has to be
  hand-maintained and gets harder to keep unambiguous as the registry grows and
  domains' vocabularies start to overlap.
- **LLM-based**: a cheap/fast model call, given a system prompt built dynamically from
  the registry's own descriptions — a new sub-agent's one-line description is enough
  for the classifier to route to it correctly, no rule-writing required. Handles
  ambiguous phrasing far better than keyword matching, at the cost of one extra small
  model call per turn.
- **Hybrid**: heuristic first, LLM fallback only when confidence is low. Best of both,
  at the cost of maintaining two mechanisms and a confidence signal to arbitrate
  between them.

Pick one as the default; keep the others viable behind the same interface as the
registry grows and the tradeoffs shift.

## Fan-out and fan-in

A single message can be routed to sub-agents in **more than one macro category at
once** — not just multiple sub-agents within one category. Each matched sub-agent runs
independently (start sequential; the execution model should be async-friendly enough
that moving to parallel execution later is a config change, not a rewrite — sub-agent
runs must not share mutable state). Results converge at a **synthesis** step that
reconciles findings across every matched sub-agent, including across macro-category
boundaries, into one answer.

## Independent verifier

A post-synthesis agent, with no domain bias of its own, that reviews the combined
answer against the original question — a check, not a contributor, sitting after
synthesis rather than alongside the other sub-agents. Two trigger models are worth
supporting behind the same design:

- **Manual**: the user (or operator) explicitly invokes it.
- **Automatic**: triggered when a condition warrants it — most usefully, when a tool or
  action involved has real-world side effects. This requires tools/actions to declare
  that fact as metadata (a `has_side_effects` flag) so the trigger condition doesn't
  need bespoke logic per domain.

Auto-triggering on every turn is rarely worth the added latency/cost; gating it on
side-effect-bearing actions targets it at the cases where a silent synthesis error
actually matters.

## Loop prevention and side-effect approval

Two safety nets are load-bearing requirements for any sub-agent implementation —
present or future, not just the ones built in a given phase — not incidental
implementation detail:

- **Loop prevention**: every sub-agent's tool-calling loop enforces a maximum round
  cap, and a guard against repeating the exact same tool call (same tool, same
  arguments) — a common real failure mode, cheaper to catch than waiting for the round
  cap. Both apply per sub-agent, independent of which provider/model is running.
  **Extended with two cheap, deterministic checks, no new infrastructure required**:
  (1) canonicalize arguments before comparing (trim whitespace, sort keys, normalize
  types) so cosmetically-different-but-identical calls still get caught; (2) track
  whether the last K tool results were all effectively unproductive (an identical
  error, repeated "not found") regardless of whether the calls themselves varied — a
  model can change its query every time and still be making zero progress, which
  call-comparison alone would never catch. **Still deliberately deferred**: embedding-
  based semantic similarity between calls, or a periodic LLM-judged "is this
  trajectory stuck" check — both add real cost/latency and false-positive risk for a
  problem the two cheap checks may already handle well enough in practice.
- **Side-effect approval gate**: a tool call flagged `has_side_effects: true` pauses
  that sub-agent's loop and requires explicit human approval before it executes —
  distinct from, and prior to, the independent verifier above. The verifier is a
  post-hoc quality check on an already-completed answer; this is a pre-execution gate
  on one specific risky action. A sub-agent must never autonomously execute a
  side-effect action without this checkpoint, regardless of how confident the model
  is — `has_side_effects` is not just metadata for a future feature, it's an
  enforcement point from the start.

## Predetermined playbooks

Assistants **execute** deployment and intake patterns; they do not invent them.
A playbook is a named, versioned, testable procedure (inputs, steps, success
checks, side-effect flags). The model may choose *which* playbook applies and
how to talk about it; it may not skip a required step, invent a new topology, or
treat a failed check as optional.

This is what keeps a conversational UI from becoming an unsupervised operator
with root. New capability is a new playbook in the product, not a cleverer
prompt.

## Phases are reviewable and rerunnable

Every phase is driven through the web UI (chat plus a structured review
surface for that phase's schema). A phase can be inspected, edited, and run
again. Steps are **idempotent** and **state-aware**: already-done work is
detected (local state, then live verification) and skipped; drift between the
two is corrected by re-running the step, not by a separate "resume" mode.

## Errors become issues

If the system hits an unexpected error — or the operator flags one — it opens
an issue with the maintainer. Validation failures ("that IP is malformed") are
field errors, not issues.

Where the issue is filed depends on what exists: a local issue record first
(always); the product's public tracker only when the operator opts in and the
classification is a product bug; the tenant's own tracker once Deploy has
created it. Issue bodies never include secret values or raw probe payloads.

## GPU / compute management

Where a deployment needs to run its own models locally, compute lifecycle management
is a layered pipeline, each stage independent of the ones above it:

1. **Host registry** — any compute host (local machine, remote VM, dedicated hardware)
   is a registry entry, not a hardcoded target.
2. **Resource discovery** — enumerate what a host actually has (GPUs, etc.), locally or
   over a remote connection.
3. **Cluster formation** (optional) — when a deployment spans multiple hosts, form
   whatever clustering layer is needed before deploying to it.
4. **Deployment** — start the actual model-serving workload on the resolved target
   (single host or cluster).
5. **Validation** — smoke-test before marking a deployment usable.

Scope this incrementally: single-host/single-resource first, multi-resource and
multi-host clustering as a later phase — the pipeline shape doesn't change, only how
much of it is automated.

**Don't auto-manage shared resource lifecycle without usage tracking.** If a resource
(e.g. a loaded model) can be used concurrently by more than one agent, track who's
using it (a reference count is enough) before allowing any automated or manual
teardown — otherwise an in-flight call can be disrupted by an unrelated decision
elsewhere in the system. This holds whether or not dynamic (automatic) lifecycle
management is built yet; build the tracking first, automate teardown decisions later.

## Secrets

Treat secrets as fetched, not stored. Once a secrets backend exists, the app
authenticates to it via a machine identity, and fetches everything else —
provider API keys, tool credentials, database credentials — from there. The only
thing that has to exist in plaintext locally is the credential needed to reach
the secrets backend itself (the unavoidable "secret zero"); everything
downstream of that is fetched, not configured.

**Bootstrap is the exception that makes the rule possible.** Before a secrets
backend exists, the bootstrap profile *is* secret-zero: values live on the
control-plane host, behind the same secrets-client interface, never in the
product repo. Deploy's job includes standing up the real backend and migrating
those references. Callers should not care which backend implemented `get`.

## Host/service registry and provenance

Any external system the harness depends on (a host, a service endpoint, a credential
reference) is a registry entry, not a hardcoded value. Each entry should carry a
**provenance**: `provisioned` (the harness created it), `discovered` (an existing
system, registered by reference), `manual` (an operator added it directly, e.g. through
a settings UI), or `declared` (it came from applying a desired-state config file — see
below). Distinguishing `manual` from `declared` matters because they have different
recovery stories: a `manual` entry only exists in the database; a `declared` entry can
be recreated by reapplying its source file.

### Configuration is not one thing

Registry-shaped state is best split by what kind of thing it is:

- **Bootstrap/static config** — the minimum needed before the app can reach its own
  database or secrets backend at all (a DB connection string, the credential for the
  secrets backend itself — or, in the bootstrap profile, the local secret-zero
  store). Necessarily local to the control plane, not product-repo content.
- **Declarative config** — registry entries that represent *intent* and change rarely:
  which hosts/services exist, which sub-agents are registered and what they're
  configured with. This is a good fit for a desired-state file (YAML/JSON) applied into
  the database via an idempotent, diffable apply step — the same pattern as
  infrastructure-as-code tooling (`terraform apply`, `ansible-playbook`, `kubectl
  apply`). The file references secrets by name/path in the secrets backend, never by
  value. Losing the database becomes "reapply the file," not "restore a backup and hope
  it's current." The bootstrap foundations bundle is the first document of this kind.
- **Operational/runtime data** — conversation history, job execution records, usage
  logs. This has no meaningful "desired state" and only ever exists because the system
  ran. No file representation makes sense; back it up the way any database is backed
  up (dump/point-in-time recovery).

**Drift handling default**: when applying a desired-state file, the file wins — the
apply step reconciles the database to match it, the same behavior as the IaC tools it's
modeled on. A dry-run diff should be available before an apply commits, so nothing is
silently overwritten, but the resolution model itself favors the file over
out-of-band changes (e.g. a direct settings-UI edit that was never captured in the
file). This is a starting default, not load-bearing — revisit if it proves too blunt in
practice.

## Bootstrap: the installer problem

A harness whose own operational domain (managing infrastructure) is implemented as
in-app agents runs into a chicken-and-egg problem: those agents can't provision the
infrastructure the harness itself needs to run, because nothing is alive yet to run
them.

The resolution is a **thin installer** whose only job is to start a control
plane, then get out of the way. That control plane *is* The Shed, running a
bootstrap profile — not a second product, and not a special-case "installer
mode" inside a different app. The installer does not provision Git, Kubernetes,
DNS, or a secrets backend. It holds enough information, validated and probed,
that the Deploy phase can start.

Two intake modes converge on the same foundations schema, differing only in
provenance of what the operator *intends* to do later:

- **Build** (net-new): the operator will ask Deploy to create the thing.
- **Adopt** (import existing): the operator already has the thing; Deploy will
  register it by reference.

Bootstrap records the choice and the connection facts. It does not create or
adopt anything except the control plane itself.

Whether that control plane later retires, becomes break-glass, or moves onto
the platform Deploy builds is a Deploy-phase decision, not a Bootstrap one.

## Product vs. tenant

The harness itself is **one product** with one canonical, public source. A
**deployment is a tenant** of that product. Tenant-specific values — hosts,
credentials, which sub-agents are registered, later a private Fleet repo —
never live in the product repo.

Build and Run are **jobs of the product**, not products in their own right:
when exercised, they act on a specific tenant's state.

A tenant's durable operating state will eventually live in that tenant's own
private repo (the Fleet model sketched in earlier design). That repo does not
exist in Bootstrap. Until it does, the tenant's state is local to the bootstrap
control plane and exportable as the foundations bundle.

**Application visibility defaults private.** Anything Build produces for a tenant is
private (stored in that tenant's own git hosting) unless explicitly flagged public, in
which case it's stored on the product's public git host instead. Visibility is a
property of the individual application, decided when it's created — not inferred, not
inherited from where the harness itself lives.

**Every repo carries an `AGENTS.md` scoped to what that repo actually is.** The same
convention serves two audiences at once: an AI coding tool helping build the product,
and a Build sub-agent later doing real work in a codebase — both are agents operating
on a repo, and neither should have to rediscover repo-specific conventions by trial
and error. Scope its content narrowly; it points at the real docs rather than
restating them, and it never carries content that belongs in the other tier (no
tenant specifics in the product's `AGENTS.md`, no product-architecture restatement in
a tenant's).

## Multi-tenancy from day one

Even a single-user deployment should model users, roles, and ownership as first-class
from the start — every session/task/memory record owned by a user, roles attached to a
user even if only one exists today. This is materially cheaper to build in from the
beginning than to retrofit once real data and integrations depend on the shape of that
data.

## Identity/auth as pluggable providers

Model local password authentication as one identity-provider type among several (a
separate identities/providers relation keyed to the user, not credentials fields baked
directly into the user record), so additional providers (OAuth, SSO, etc.) are additive
later, not a restructuring.

The first user on a new tenant is created by the bootstrap setup gate — not a
public signup, and not a declarative apply that depends on a repo that does not
exist yet.

## Testing discipline

Split what's tested by what kind of thing it is:

- **Deterministic code** — routing logic, registries, provider abstractions,
  orchestration mechanics, resource lifecycle tracking, foundations schema
  validation, playbook step machines, probe checks against mocked endpoints —
  gets strict test-first development, with any LLM calls mocked so tests stay
  fast and deterministic.
- **LLM-facing behavior** — does a classifier route a given phrasing correctly, does a
  sub-agent's system prompt produce a good answer, does synthesis actually reconcile
  results well — is not pass/fail in the unit-test sense. This is what tracing/eval
  tooling is for, kept as a separate concern from the test suite, not a substitute for
  it and not judged by it.
