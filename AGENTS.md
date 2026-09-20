# Agent guidance — The Shed (product)

For any AI agent working in this repo — a coding assistant, or one of The Shed's own
`build` sub-agents doing real work in a codebase. Same convention either way.

Before touching a subsystem, read its pair: `docs/prd/<subsystem>.md` (why, what) and
`docs/spec/<subsystem>.md` (how). Read `docs/architecture.md` before anything
cross-cutting, and `docs/mvp.md` before treating a later phase as in scope. Grill
records in `docs/grill/` explain how a shape was decided; the PRD/SPEC remain
source of truth after a grill lands. If the code disagrees with the docs, that's
a bug in one of the two, not a cue to improvise a third answer.

Test-first, always. See "Testing discipline" in `docs/architecture.md` for what that
does and doesn't cover.

This repo holds the product only — no tenant-specific values, hosts, or credentials.
That content belongs on the tenant's control plane (Phase 1: the bootstrap LXC)
and later in a tenant's own Fleet repo. See `docs/architecture.md`,
"Product vs. tenant". If a change would put an environment specific here, it's in
the wrong repo.

The product GitHub repository is `andrewkriley/shedlife.ai`. `theshed` is the
product and release-please package name, and it may be the local checkout
folder. It is not the GitHub identity. `andrewkriley/theshed` is the pre-rename
slug; GitHub still redirects it. Cursor Cloud Agents record `repoUrl` at launch
from the Cursor project or the self-hosted worker's git remote. The PR tool
requires a PR URL to match that recorded repo. A run bound to
`github.com/andrewkriley/theshed` can push (redirects work) and sometimes
*create* PRs on `shedlife.ai`, but `update_pr` and `get_ci_status` fail with
"PR URL must belong to the current repository." That binding cannot be patched
from inside the run. Confirm `run-info.repoUrl` and the worker's registered
repos are `github.com/andrewkriley/shedlife.ai` before using the PR tool. If
they still say `theshed`, point the worker checkout's `origin` at
`https://github.com/andrewkriley/shedlife.ai.git`, restart the worker from that
directory, and start a **new** Cloud Agent from `andrewkriley/shedlife.ai`. Do
not keep a theshed-bound agent for PR updates. On a mismatched run, use the
GitHub API and tell the operator to relaunch.

`docs/parked/` is historical design. Do not implement from it.

Commit/PR mechanics (signing, Conventional Commits, review) are in `CONTRIBUTING.md`
— CI enforces them, so read it rather than guessing.
