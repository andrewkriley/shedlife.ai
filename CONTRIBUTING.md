# Contributing to The Shed

Thanks for considering a contribution. This document covers how to get set up, what's
expected of a change, and how it lands.

## Before you start

Read [`docs/architecture.md`](docs/architecture.md) first — it's the portable pattern
this product is built around, and it explains the reasoning behind decisions you'll
otherwise just have to take on faith. [`docs/mvp.md`](docs/mvp.md) is what is
actually in scope. [`docs/stack.md`](docs/stack.md) covers the
specific technology choices. Each subsystem also has a PRD (`docs/prd/`) and SPEC
(`docs/spec/`) pair — the PRD explains *why* and *what*, the SPEC explains *how*.
Read the relevant pair before changing that subsystem. Grill records in
`docs/grill/` are history; `docs/parked/` is not source of truth.

## Development setup

- Backend: Python + FastAPI. Frontend: React + TypeScript + Vite.
- Local dependencies (Postgres, Redis) run via `docker-compose` for development.
  In Phase 1 they also run inside the bootstrap LXC — that *is* the production
  pattern until a Deploy grill says otherwise.
- Full setup instructions land here once the repo is scaffolded (see the project's
  current status if this section still looks sparse).

## Test-driven development is not optional

This project's stated engineering practice, since its first design decisions, is
test-first for all deterministic code — routing logic, registries, orchestration
mechanics, anything that isn't an LLM call itself. Mock LLM calls in tests; they
should run fast and deterministically. LLM-facing behavior (does a classifier route a
given phrasing correctly, does a prompt produce a good answer) isn't judged by unit
tests — that's what tracing/eval tooling is for. See "Testing discipline" in
`docs/architecture.md`.

A PR that adds behavior without a test for it will be asked to add one before review
continues.

## Commit and PR conventions

- Open PRs against [`andrewkriley/shedlife.ai`](https://github.com/andrewkriley/shedlife.ai).
  `theshed` is the product / package name only. `andrewkriley/theshed` is a
  GitHub rename redirect, not the repository Cloud Agents or the PR tool should
  treat as current. Self-hosted Cursor workers take their registered repo from
  the checkout's `origin` at worker start — that remote must be
  `shedlife.ai`, then start a new Cloud Agent from this repo.
- **Commits must be signed** (GPG or SSH signing) — enforced by branch protection on
  `main`, not just a suggestion.
- **PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/)**
  (`feat: ...`, `fix: ...`, `chore: ...`, etc.) — checked in CI. This matters beyond
  style: your PR title becomes the squash-merge commit message, and that's what
  drives automatic versioning and the changelog (see `RELEASING.md`). While
  the product is `0.x`, both `fix:` and `feat:` produce a **patch**; a
  breaking change (`feat!:` or a `BREAKING CHANGE:` footer) produces a
  minor. After `1.0.0` the usual SemVer mapping applies.
- PRs merge via **squash merge only** — keep your branch's own commit history however
  you like while working; only the final PR title matters for the record `main` keeps.

## What CI checks

Every PR runs: the test suites (backend `pytest`, frontend Vitest), linting (`ruff`,
`oxlint`), type-checking (`mypy`, `tsc --noEmit`), `commitlint` against the PR title,
`gitleaks` (secret scanning), `release-please authority` (version files only
change on a release-please PR), and a Trivy filesystem scan (known-vulnerability
scanning of dependencies, report-only for now). Once the rulesets in
`docs/spec/release-pipeline.md` are on, the required checks on `main` are
`backend (pytest, ruff, mypy)`, `frontend (vitest, oxlint, tsc)`,
`commitlint (PR title)`, `gitleaks`, and `release-please authority` — no
bypass, including the maintainer. Trivy stays report-only.

CodeQL (static analysis for code-level vulnerabilities) is part of the intended design
(see the SPEC) but isn't running yet: GitHub code scanning needs Advanced Security,
free on public repos but paid on private ones, and this repo is currently private.
Revisit once that changes.

## Review and merge

Every PR needs **one approval from someone other than its author** before it can
merge. A solo maintainer does not need a collaborator: approve agent-opened
PRs in the GitHub UI (you are not the author). GitHub will not let you
approve a PR you opened yourself — the repository admin may bypass *only*
that approval requirement. That bypass never extends to signed commits or CI
passing — those apply to every merge, no exceptions, regardless of who's
merging. See "Protecting `main`" in `RELEASING.md`.

**Release PRs are different.** A PR titled `chore(main): release theshed …` (the
standing `release-please` PR) is merged only by a maintainer in the GitHub UI.
Cloud Agents and workers must not merge it, dispatch the release workflow, or
create tags. See `RELEASING.md`.

## Questions

Open an issue if something in this document — or in the design docs it points to —
doesn't match what you're seeing in the repo. The docs are the source of truth for
intent; if the code and the docs disagree, that's a bug in one of them worth flagging.
