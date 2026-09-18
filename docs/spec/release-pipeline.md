# Release Pipeline — SPEC

Status: draft, technical design for
[`../prd/release-pipeline.md`](../prd/release-pipeline.md). References
[`../stack.md`](../stack.md), the [Bootstrap SPEC](./bootstrap.md) (`apps/` Fleet
layer, pinned-tag pattern), and the existing `gitleaks` GitHub Actions workflow this
extends rather than replaces.

## Actors / components

- **GitHub Actions** — CI platform, already running `gitleaks`; this adds test and
  build/publish jobs alongside it, not a separate CI system.
- **Test suites** — `pytest` (backend), Vitest/React Testing Library (frontend).
- **GitHub Container Registry (GHCR)** — holds versioned, published images, tied to
  the public `andrewkriley/theshed` repo.
- **A tenant's Fleet repo** (`apps/` layer) — the thing that actually determines what
  a given tenant runs, by referencing an image tag/digest.

## Sequence (release, happy path)

1. A commit is pushed / a PR is opened against `theshed`.
2. GitHub Actions runs: `gitleaks` (existing), `pytest`, and the frontend test suite,
   in parallel. Any failure blocks merge.
3. On merge to `main`: same gate re-runs (protects against a bad merge commit, not
   just the PR's own branch state).
4. On a tagged release: the test gate re-runs as a prerequisite; on success, the
   container image builds and publishes to GHCR under that version tag.
5. **Nothing here touches any tenant's Fleet repo.** A tenant operator, separately and
   deliberately, edits their own Fleet repo's `apps/` layer to reference the new tag —
   the same declarative-apply mechanism as any other Fleet change (Bootstrap SPEC) —
   and Flux reconciles their cluster to it on its own schedule.

## Data

No new application data — this is a CI/build pipeline, not a runtime subsystem. The
only durable artifacts are the published images in GHCR (versioned by tag) and each
tenant's own Fleet repo state (already covered elsewhere).

## Interfaces

- GitHub Actions workflow files (`.github/workflows/`) — `test.yml` (pytest +
  frontend suite, on push/PR), `release.yml` (build + publish, on tag), alongside the
  existing `gitleaks.yml`.
- No new backend/frontend API surface — this subsystem doesn't run inside The Shed
  itself.

## Security model

- Published images are only ever built from a commit that passed the full test gate —
  no path to publish an untested image.
- GHCR access for publishing uses GitHub Actions' own scoped `GITHUB_TOKEN` (same
  mechanism the `gitleaks` workflow already uses for its own permissions), not a
  separately-managed credential.
- A tenant pulling an image doesn't need any credential tied to another tenant's
  infrastructure — consistent with the PRD's reasoning for choosing GHCR over a
  tenant-hosted registry.

## Open items

None remaining from this design pass.
