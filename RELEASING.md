# Releasing The Shed

Releases are automatic in mechanism, deliberate in timing — versioning and the
changelog are generated for you; *when* a release actually ships is still a maintainer
decision, made by merging one specific PR.

## How it works

1. Every PR that merges to `main` has a [Conventional Commits](https://www.conventionalcommits.org/)
   -formatted title (enforced in CI — see `CONTRIBUTING.md`).
2. `release-please` watches `main` and maintains a standing **Release PR** — as
   `fix:`/`feat:`/etc. commits land, it keeps that PR's changelog and version bump
   up to date. You don't create or edit this PR by hand.
3. **Merging the Release PR is what actually cuts a release.** Nothing ships until a
   maintainer does this deliberately — a string of merged feature/fix PRs alone never
   triggers a release on its own.
4. On merge, `release-please` tags the release (`vMAJOR.MINOR.PATCH`) and creates a
   GitHub Release with the generated changelog. The same job attaches
   `bootstrap/install.sh` to that release. A separate `release: published`
   workflow cannot do this — `GITHUB_TOKEN` is not allowed to start a second
   workflow after it creates the tag.
5. The tag triggers the build pipeline: the full test gate re-runs, the container
   image builds, gets scanned (Trivy) for known vulnerabilities, and — only if that
   passes — publishes to GitHub Container Registry under the new version tag.
   The attached script is what this one-liner fetches:

   `curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash`

## Version numbers

[Semantic Versioning](https://semver.org/), derived from commit types. While
the product is `0.x` we keep the **patch** number moving — lots of small
edits should be `0.4.1`, `0.4.2`, not a new minor each time.

| Commit type | While `0.x` | After `1.0.0` |
|---|---|---|
| `fix:` | patch (`0.4.Z`) | patch |
| `feat:` | patch (`0.4.Z`) | minor |
| `feat!:` or `BREAKING CHANGE:` | minor (`0.Y.0`) | major |
| `chore:`, `docs:`, `ci:`, etc. | no bump | no bump |

`1.0.0` is a deliberate later decision, not something a single `feat!:` can
force while we are still in Bootstrap. Operator-visible small edits (README
install command, UI copy, installer) should be `fix:` if they need a new
tag; `docs:` is for internal design notes that do not need a pin.

## What a release does *not* do

**Publishing a release does not deploy it anywhere.** Every tenant's deployment is
independent. In Phase 1 the operator adopts a new version by pointing the
bootstrap LXC at the new image tag (re-running the pinned install script, or
an equivalent pull). After Deploy, the same idea becomes an edit to that
tenant's Fleet repo — see the Bootstrap PRD and the Deploy stub. A GitHub
release landing is an announcement that a version exists and is available to
pull, not an instruction that anyone must pull it.

## If you're not a maintainer

You don't need to think about any of this to contribute — just follow
`CONTRIBUTING.md`'s commit/PR conventions. Everything above happens after your PR
merges, without any action on your part.
