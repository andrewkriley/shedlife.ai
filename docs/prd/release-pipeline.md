# Release Pipeline — PRD

Status: draft. See [`../spec/release-pipeline.md`](../spec/release-pipeline.md) for
the technical design this PRD drives, and [`../architecture.md`](../architecture.md)
("Testing discipline"), the [Bootstrap PRD](./bootstrap.md) (the `apps/` Fleet layer,
pinned-release-tag pattern already used for the bootstrap script), and the
[Stack](../stack.md) reference for what this document builds on.

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

## Open questions

None remaining from this design pass.
