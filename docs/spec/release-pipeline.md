# Release Pipeline — SPEC

Status: draft, technical design for
[`../prd/release-pipeline.md`](../prd/release-pipeline.md). References
[`../stack.md`](../stack.md), the [Bootstrap SPEC](./bootstrap.md) (pinned-tag
install script; the LXC pulls this image), the [Deploy stub](../prd/deploy.md)
(later Fleet `apps/` layer), and the existing `gitleaks` GitHub Actions
workflow this extends rather than replaces.

## Actors / components

- **GitHub Actions** — CI platform, already running `gitleaks`; this adds test,
  lint/type-check, security-scan, versioning, and build/publish jobs alongside it, not
  a separate CI system.
- **Test suites** — `pytest` (backend), Vitest/React Testing Library (frontend).
- **Lint/type-check** — `ruff` + `mypy` (backend), ESLint + `tsc --noEmit` (frontend).
- **`commitlint`** — enforces Conventional Commits format on PR titles.
- **CodeQL** — GitHub's native SAST, scanning application code.
- **Image scanner** (e.g. Trivy) — scans the built container image before publish.
- **`release-please`** — opened or refreshed by a maintainer (Actions → Run
  workflow on `main`; optionally later on push to `main`). Maintains an
  accumulating Release PR with the changelog; tags and cuts a GitHub Release
  after that PR is merged in the GitHub UI.
- **Maintainer (human)** — the only actor who may start `release-please.yml`,
  approve the `release` environment, or merge a Release PR. Cloud Agents,
  self-hosted workers, and other bots are not this actor.
- **GitHub Environment `release`** — required-reviewer gate on the
  `release-please` job; deployment branches limited to `main`.
- **GitHub Container Registry (GHCR)** — holds versioned, published images, tied to
  the public `andrewkriley/shedlife.ai` repo.
- **A tenant's Fleet repo** (`apps/` layer) — the thing that actually determines what
  a given tenant runs, by referencing an image tag/digest.

## Branch protection (two GitHub Rulesets on `main`, not one)

| Ruleset | Rules | Bypass |
|---|---|---|
| A | Require signed commits; require all CI status checks to pass (test, lint, type-check, `commitlint`, CodeQL, image scan); require linear history (squash merge only, PR title as commit message) | None, for anyone |
| B | Require pull request before merging; require 1 approval, not from the PR author | Repository Admin role only |

Two rulesets, not one, so admin bypass can be scoped to just the peer-approval
requirement (Ruleset B) — signing and the full CI gate (Ruleset A) apply
unconditionally, including to an admin's own merge.

## Sequence (release, happy path)

1. A commit is pushed / a PR is opened against the product GitHub repo
   (`andrewkriley/shedlife.ai`), with a Conventional-Commits-formatted title.
   The release-please package name remains `theshed`.
2. GitHub Actions runs, in parallel: `gitleaks` (existing), `pytest` + frontend tests,
   lint + type-check, `commitlint` on the PR title, CodeQL. Any failure blocks merge
   (Ruleset A).
3. PR merges (squash, PR title becomes the commit message) once Ruleset A's checks
   pass and Ruleset B's approval requirement is satisfied or bypassed.
4. A maintainer starts `release-please` from the Actions tab on `main` (the
   `release` environment must be approved in the GitHub UI). The job reads
   commits since the last tag and opens or updates the standing Release PR
   (version bump + changelog entry, per Conventional Commits). Config:
   `bump-patch-for-minor-pre-major` and `bump-minor-pre-major` so `0.x`
   stays patch-granular (`feat:`/`fix:` → patch; breaking → minor).
5. The maintainer reviews and merges *that* Release PR in the GitHub UI —
   not via the API, `gh pr merge`, or an agent. Then `release-please` runs
   again (second **Run workflow** while dispatch-only; automatic on push
   if that trigger is re-enabled), tags the release, and cuts a GitHub Release.
6. The tag triggers: the full test gate re-runs as a prerequisite; on success, the
   container image builds, gets scanned (Trivy), and — only if the scan passes —
   publishes to GHCR under that version tag.
7. **Nothing here touches any tenant's Fleet repo.** A tenant operator, separately and
   deliberately, edits their own Fleet repo's `apps/` layer to reference the new tag —
   the same declarative-apply mechanism as any other Fleet change (Bootstrap SPEC) —
   and Flux reconciles their cluster to it on its own schedule.

## Data

No new application data — this is a CI/build pipeline, not a runtime subsystem. The
only durable artifacts are the published images in GHCR (versioned by tag), the
`CHANGELOG.md` `release-please` maintains, and each tenant's own Fleet repo state
(already covered elsewhere).

## Interfaces

- GitHub Actions workflow files (`.github/workflows/`) — `ci.yml` (test, lint,
  type-check, `commitlint`, CodeQL, on push/PR), `release-please.yml`
  (versioning; `environment: release`; attaches `bootstrap/install.sh` in the
  same job that cuts the GitHub Release, because `GITHUB_TOKEN` cannot start
  a follow-on workflow),
  `attach-install-script.yml` (fallback for UI-published releases),
  `release.yml` (build + scan + publish, on tag), alongside the existing
  `gitleaks.yml`.
- Two Rulesets on `main` (GitHub repository settings, not a workflow file).
- GitHub Environment `release` (repository settings): required reviewers;
  deployment branches = `main` only.
- `.github/CODEOWNERS` on `CHANGELOG.md` and `.release-please-manifest.json`,
  with "require review from Code Owners" on `main`.
- No new backend/frontend API surface — this subsystem doesn't run inside The Shed
  itself.

## Security model

- Published images are only ever built from a commit that passed the full test gate
  *and* the image scan — no path to publish an untested or known-vulnerable image.
- Signed commits and the full CI gate are unconditional (Ruleset A, no bypass for
  anyone) — the only bypassable requirement is peer approval (Ruleset B), and only for
  the Repository Admin role. That bypass applies to ordinary feature PRs; it is
  not permission for an agent to merge a Release PR or dispatch `release-please`.
- A version is cut only after a human merges the Release PR in the GitHub UI
  and the `release` environment has been approved by a required reviewer.
- GHCR access for publishing uses GitHub Actions' own scoped `GITHUB_TOKEN` (same
  mechanism the `gitleaks` workflow already uses for its own permissions), not a
  separately-managed credential.
- A tenant pulling an image doesn't need any credential tied to another tenant's
  infrastructure — consistent with the PRD's reasoning for choosing GHCR over a
  tenant-hosted registry.

## Open items

None remaining from this design pass.
