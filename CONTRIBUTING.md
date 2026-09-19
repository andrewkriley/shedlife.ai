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
`gitleaks` (secret scanning), and a Trivy filesystem scan (known-vulnerability
scanning of dependencies, report-only for now). All of these must pass before merge —
this is enforced unconditionally, for every contributor, with no bypass, once branch
protection is actually turned on (see "Branch protection" in
`docs/spec/release-pipeline.md` — not yet enabled as of this writing).

CodeQL (static analysis for code-level vulnerabilities) is part of the intended design
(see the SPEC) but isn't running yet: GitHub code scanning needs Advanced Security,
free on public repos but paid on private ones, and this repo is currently private.
Revisit once that changes.

## Review and merge

Every PR needs **one approval from someone other than its author** before it can
merge. This applies to everyone — including the maintainer — with one narrow
exception: a repository admin can bypass *only* the approval requirement, for the
practical reason that a single-maintainer project has no peer available to provide
one yet. That bypass never extends to signed commits or CI passing — those apply to
every merge, no exceptions, regardless of who's merging.

## Questions

Open an issue if something in this document — or in the design docs it points to —
doesn't match what you're seeing in the repo. The docs are the source of truth for
intent; if the code and the docs disagree, that's a bug in one of them worth flagging.
