# The Shed — Architecture

This document describes the **portable pattern**: the parts of the design that don't
depend on any particular environment, provider, or tool. It contains no URLs, tokens,
credentials, or references to any specific deployment. Anyone building a similar
agentic harness could apply this document as-is.

For the specific technologies chosen to implement this pattern in this deployment, see
[`stack.md`](./stack.md).

---

## What this is

A web-based, agentic-first AI harness built around fan-out/fan-in orchestration of
agents and sub-agents, capable of using a mix of AI model providers (cloud and local).

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
  **Known gap, not solved**: the repeated-call guard only catches exact-identical
  calls — a model that varies one argument slightly each time would evade it while
  still being effectively stuck. Fuzzy/near-duplicate detection is a harder problem,
  documented here as unsolved rather than papered over.
- **Side-effect approval gate**: a tool call flagged `has_side_effects: true` pauses
  that sub-agent's loop and requires explicit human approval before it executes —
  distinct from, and prior to, the independent verifier above. The verifier is a
  post-hoc quality check on an already-completed answer; this is a pre-execution gate
  on one specific risky action. A sub-agent must never autonomously execute a
  side-effect action without this checkpoint, regardless of how confident the model
  is — `has_side_effects` is not just metadata for a future feature, it's an
  enforcement point from the start.

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

Treat secrets as fetched, not stored. The app authenticates to an external secrets
backend via a machine identity, and fetches everything else — provider API keys, tool
credentials, database credentials — from there. The only thing that has to exist in
plaintext locally is the credential needed to reach the secrets backend itself (the
unavoidable "secret zero"); everything downstream of that is fetched, not configured.

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
  secrets backend itself). Necessarily a local file, not registry data — this is the
  unavoidable "secret zero."
- **Declarative config** — registry entries that represent *intent* and change rarely:
  which hosts/services exist, which sub-agents are registered and what they're
  configured with. This is a good fit for a desired-state file (YAML/JSON) applied into
  the database via an idempotent, diffable apply step — the same pattern as
  infrastructure-as-code tooling (`terraform apply`, `ansible-playbook`, `kubectl
  apply`). The file references secrets by name/path in the secrets backend, never by
  value. Losing the database becomes "reapply the file," not "restore a backup and hope
  it's current."
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
them. The resolution is to keep the **first bootstrap outside the running app**, in a
thin, standalone installer that does one job — get a minimal control plane alive — and
then hands off. Everything after that flows through the harness's own normal
capabilities; there is no special-case "installer mode" inside the running app.

Two installer modes converge on the same registry, differing only in provenance:

- **Build** (net-new): given credentials for a raw compute substrate, provision what's
  needed (a host, a runtime, a database, a secrets store) from nothing, then deploy and
  hand off. Registry entries get created.
- **Adopt** (import existing): given endpoints/credentials for systems that already
  exist, discover what's there via each system's own API and register it by reference.
  Nothing is created.

Both paths end at the same place: a running control plane with a populated registry.
The installer's job is exactly the gap between "nothing running" and "the harness can
take over" — keep it that thin.

## Product vs. tenant

The harness itself (the bootstrap orchestrator and the ongoing Assist/Build/Run
engine) is **one product** with one canonical, public source. A **deployment is a
tenant** of that product, and a tenant's entire operating state — its registered
hosts/services/sub-agents, its GitOps manifests, everything specific to that
deployment — lives in its own private repo, separate from the product's source. Build
and Run are **capabilities of the product**, not products in their own right: when
exercised, they act on a specific tenant's state, not on the product's own repo. See
the Bootstrap & Fleet Provisioning PRD/SPEC for how a tenant's infrastructure and this
private repo actually get stood up.

This separation is what makes "the same product, deployed independently by different
tenants" coherent: the product repo has no tenant-specific content in it at all, and
every tenant-specific detail — network addresses, credentials-by-reference, which
sub-agents are registered — lives in that tenant's own private repo instead.

**Application visibility defaults private.** Anything Build produces for a tenant is
private (stored in that tenant's own git hosting) unless explicitly flagged public, in
which case it's stored on the product's public git host instead. Visibility is a
property of the individual application, decided when it's created — not inferred, not
inherited from where the harness itself lives.

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

## Testing discipline

Split what's tested by what kind of thing it is:

- **Deterministic code** — routing logic, registries, provider abstractions,
  orchestration mechanics, resource lifecycle tracking — gets strict test-first
  development, with any LLM calls mocked so tests stay fast and deterministic.
- **LLM-facing behavior** — does a classifier route a given phrasing correctly, does a
  sub-agent's system prompt produce a good answer, does synthesis actually reconcile
  results well — is not pass/fail in the unit-test sense. This is what tracing/eval
  tooling is for, kept as a separate concern from the test suite, not a substitute for
  it and not judged by it.
