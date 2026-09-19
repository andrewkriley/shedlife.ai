# Run (phase) — PRD

Status: **awaiting grill**. Not MVP. This is the **Run phase** (AI Ops,
patrols), not the Run *job*. See [`../mvp.md`](../mvp.md) and
"Lifecycle phases are not jobs" in [`../architecture.md`](../architecture.md).

## Intent (not yet designed)

Operate the platform the earlier phases stood up: patrols, AI Ops, the
ongoing Run job with a growable registry of operational sub-agents. Same
phase rules: TDD, web UI + assistant, predetermined playbooks, reviewable /
rerunnable / idempotent, errors become issues.

The Run *job* (macro category) and pieces like `run.network` are already
described in the Core Agentic Loop docs. This phase is the operational
practice and the playbooks around it — not a second routing dimension.

No SPEC until that grill lands.
