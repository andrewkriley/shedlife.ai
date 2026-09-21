# Release Pipeline — PRD

Status: draft. Fleet-repo image pull is **Deploy-era**; the bootstrap LXC
already needs the same GHCR image and the same pinned-tag install script.
See [`../spec/release-pipeline.md`](../spec/release-pipeline.md) for the
technical design this PRD drives, and [`../architecture.md`](../architecture.md)
("Testing discipline"), the [Bootstrap PRD](./bootstrap.md) (pinned-release-tag
install script), the [Deploy stub](./deploy.md) (later Fleet `apps/` layer),
and the [Stack](../stack.md) reference for what this document builds on.

## Problem

TDD has been a stated hard requirement since the very first design decisions, but
nothing has actually specified where tests run, what gates a change from reaching a
tenant, how The Shed's own container image gets built, or where that image lives
between being built and a tenant's Flux instance deploying it.

## Goals

- Tests (backend and frontend) run automatically on every change, gating merge — not
  a manual, easy-to-skip step.
- A versioned, reproducible container image is the actual deployable artifact — not
  "whatever the Fleet repo happens to reference."
- Deploying a new version to any given tenant is that **tenant's own deliberate
  action**, not something a product release pushes onto them unasked.
- Versioning and changelog generation are automatic, driven by commit discipline —
  not a manual "what should the next version be" decision each time.
- **Cutting a version is a human GitHub UI action.** Cloud Agents, workers, and
  other bots may land work on `main`; they must not merge a Release PR, dispatch
  `release-please`, or create tags. That is the SDLC split between development
  and release.
- `main` is protected the same way regardless of who's merging — commit signing and a
  passing CI gate apply unconditionally, including to the maintainer's own merges;
  only the *peer-approval* requirement can ever be bypassed, and only because a
  single-maintainer project has no peer to provide one yet.

## Non-goals (this phase)

- Automatic image-update propagation to tenants (Flux's own image-automation
  capability exists and could do this later) — opt-in roadmap, not default behavior.
- Multi-architecture image builds, staged/canary rollouts — not addressed this phase.

## Users

- Contributors to the product (CI enforces the testing discipline on them).
- Tenant operators, who decide when their own deployment updates.

## Success criteria

- A pull request with a failing test cannot merge.
- A tagged release produces a versioned, pullable container image, reachable by any
  tenant — including a future tenant with no access to this operator's own
  infrastructure.
- Updating a tenant's running version is a visible, deliberate change to that tenant's
  own Fleet repo — never a side effect of a product release landing on GitHub.

## Requirements

### Where the registry lives — and why this is *not* the same call as the Fleet repo

The Fleet repo is a continuously-polled runtime dependency (Flux reconciles against
it on an interval) — that's why it has to be self-hosted, per the Bootstrap design. A
container registry is different in kind: with the standard Kubernetes image-pull
policy, an image is pulled once per version (not on every reconciliation tick), so
depending on it is much closer to "fetch a release artifact occasionally" — the same
category as the bootstrap script itself, which already lives on public GitHub. And
critically: a **future tenant, standing up their own independent deployment, needs to
pull the same published image without needing access to any specific existing
tenant's self-hosted infrastructure** — a tenant-hosted registry can't serve that; a
product-level one can. So: **GitHub Container Registry, tied to the public product
repo** — consistent with "GitHub is for deployment [artifacts]," not a violation of
the self-hosting principle, because it isn't the same kind of dependency as the Fleet
repo.

### Test gate

Backend (`pytest`) and frontend (Vitest/React Testing Library) suites run on every
push/PR, on the same CI platform already running gitleaks (GitHub Actions) — not a
new, separate CI system. A failing test blocks merge.

### Build and publish

On a tagged release: build the container image, run the test gate as a prerequisite
(never publish an image that hasn't passed it), publish to the registry above with a
version tag.

### Tenant deployment is a pull, not a push

A tenant updates by changing the image tag/digest their own Fleet repo's `apps/`
layer references — a deliberate edit to their own repo, the same declarative-apply
mechanism as any other Fleet change. A product release does not, by itself, change
what any tenant is running.

### Versioning and changelog

Semantic Versioning (`MAJOR.MINOR.PATCH`), driven by Conventional Commits
(`feat:`/`fix:`/etc.) rather than a manual per-release decision. While the
product is `0.x`, `feat:` and `fix:` both bump **patch** so frequent small
edits stay granular (`0.4.1`, `0.4.2`); a breaking change bumps minor, not
1.0. After `1.0.0` the usual mapping applies (`feat:` minor, breaking
major). PR titles (which become the squash-merge commit message, see below)
are format-checked in CI, since they're what the versioning/changelog
tooling actually reads.

### Human release authority

A Release PR (`chore(main): release theshed …`) is merged only by a maintainer
in the GitHub pull-request UI. The `release-please` workflow is started from
the Actions tab (or, if push-to-`main` is later re-enabled, only to *update*
the standing PR — merge remains human). The GitHub Environment `release` on
that workflow requires a human reviewer and is limited to `main`.
`.github/CODEOWNERS` covers the files `release-please` bumps so Code Owner
review can be required on `main`.

This is not the same as the Ruleset B admin bypass for ordinary feature PRs.
An agent merging its own work to `main` does not get to ship a version.

### Branch protection on `main`

Two separate rulesets, not one, so a bypass can be scoped narrowly rather than
granted as a blanket exception:

- **No bypass, for anyone, ever**: signed commits required; all CI status checks
  (test gate, lint, type-check, CodeQL, image scan) must pass; linear history
  (squash merge only, PR title as the resulting commit message).
- **Bypassable by the Repository Admin role only**: PR required (no direct pushes),
  1 approval required and not from the PR's author.

The split matters: a maintainer merging their own solo work can skip waiting for a
second human's approval, but cannot skip signed commits or a failing check by virtue
of being admin — those guarantees hold unconditionally, for everyone, always. As real
contributors join, the bypass becomes something the maintainer simply stops using,
not a rule that needs restructuring.

### Additional CI

Beyond the existing `gitleaks` and the test gate above: linting (`ruff`, ESLint);
type-checking (`mypy`, `tsc --noEmit`); `commitlint` (enforces the Conventional
Commits format the versioning tooling depends on); **CodeQL** (GitHub's native SAST —
genuinely distinct from `gitleaks`, which finds committed secrets, not code-level
vulnerabilities); a container image vulnerability scan (e.g. Trivy) before publish, so
a vulnerable base layer or baked-in dependency is caught before it ever reaches the
registry, not after. Dependabot enabled as a repository setting (not a CI job) for
automated dependency-vulnerability PRs.

### Contribution guide

`CONTRIBUTING.md` (dev setup, the TDD/testing expectation, commit-signing and
Conventional Commits requirements, the branch/PR workflow) and a short `RELEASING.md`
(how a release actually gets cut, for anyone who becomes a maintainer) — written to
describe the process above once it's confirmed and built, not ahead of it.

## Open questions

None remaining from this design pass.
