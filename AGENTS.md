# Agent guidance — The Shed (product)

For any AI agent working in this repo — a coding assistant, or one of The Shed's own
`build` sub-agents doing real work in a codebase. Same convention either way.

Before touching a subsystem, read its pair: `docs/prd/<subsystem>.md` (why, what) and
`docs/spec/<subsystem>.md` (how). Read `docs/architecture.md` before anything
cross-cutting. These docs are the source of truth for intent — if the code disagrees
with them, that's a bug in one of the two, not a cue to improvise a third answer.

Test-first, always. See "Testing discipline" in `docs/architecture.md` for what that
does and doesn't cover.

This repo holds the product only — no tenant-specific values, hosts, or credentials.
That content belongs in a tenant's own Fleet repo (see `docs/architecture.md`,
"Product vs. tenant"). If a change would put an environment specific here, it's in
the wrong repo.

Commit/PR mechanics (signing, Conventional Commits, review) are in `CONTRIBUTING.md`
— CI enforces them, so read it rather than guessing.
