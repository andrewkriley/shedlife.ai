# Releasing The Shed

**A release is a human action in the GitHub UI.** Cloud Agents, self-hosted
workers, and other automation must not merge a Release PR, dispatch the
release workflow, or create tags. That split is the SDLC gate: development
lands on `main`; versioning waits for a maintainer.

**Automatic versioning is off** while Bootstrap is still in development:
`.github/workflows/release-please.yml` runs only via **Actions → release-please
→ Run workflow**. Re-enable `on.push.branches: [main]` on that workflow when we
want the standing Release PR to update as commits land. Even then, nothing
ships until a human merges that PR in the GitHub UI.

Releases are automatic in mechanism, deliberate in timing — versioning and the
changelog are generated for you; *when* a release actually ships is still a
maintainer decision.

## Who may cut a release

| Action | Who | Where |
|---|---|---|
| Merge a feature/fix PR to `main` | contributor / agent, after CI | GitHub PR |
| Start `release-please` | maintainer only | Actions tab → Run workflow, on `main` |
| Merge the Release PR | maintainer only | GitHub PR UI (Merge pull request) |
| Create a tag or GitHub Release by hand | nobody — `release-please` does this after the Release PR merges | — |

Do **not** merge a Release PR from the API, `gh pr merge`, or an agent PR
tool. The GitHub UI is the record that a person chose to ship.

The workflow job uses the GitHub Environment `release`. In the repo settings,
that environment must require a reviewer (the maintainer) and allow `main`
only. Until those two settings exist, `environment: release` is a name with
no force — the process above is still the rule.

`CHANGELOG.md` and `.release-please-manifest.json` are owned in
`.github/CODEOWNERS`. Enable **require review from Code Owners** on `main` so
the Release PR cannot merge without that human review.

The `release-please authority` check is required on `main` (Ruleset A). It
fails any PR that edits those files unless the branch is
`release-please--branches--*` and the author is `github-actions[bot]`. That
is the CI proof the version bump came from the manual Actions run, not a
handmade commit.

## Protecting `main`

This worker cannot enable GitHub rulesets. In the repo, as the owner:

1. Settings → Rules → Rulesets → New ruleset (branch).
2. **`main: CI and signing`** — target `main`. Block force pushes and
   deletions. Require signed commits. Require linear history. Require these
   status checks, with **no bypass**:
   `backend (pytest, ruff, mypy)`, `frontend (vitest, oxlint, tsc)`,
   `commitlint (PR title)`, `gitleaks`, `release-please authority`.
3. **`main: PR and approval`** — target `main`. Require a pull request, 1
   approval, require Code Owner review. Bypass: **Repository admin** only.
   That is how you approve and merge without adding a collaborator. GitHub
   will not let you approve a PR you opened yourself; agent-opened PRs you
   approve in the UI. For your own PRs, use the admin bypass after the
   Ruleset A checks are green.

Do not add `trivy (filesystem)` as a required check — it is report-only.

## How it works

1. Every PR that merges to `main` has a [Conventional Commits](https://www.conventionalcommits.org/)
   -formatted title (enforced in CI — see `CONTRIBUTING.md`).
2. A maintainer runs **release-please** from the Actions tab (or, once
   re-enabled, a push to `main` updates the standing PR). `release-please`
   opens or refreshes a **Release PR** with the changelog and version bump.
   You don't create or edit this PR by hand.
3. **Merging the Release PR in the GitHub UI is what actually cuts a
   release.** Nothing ships until a maintainer does this deliberately — a
   string of merged feature/fix PRs alone never triggers a release on its own.
4. After that merge, `release-please` must run again to tag
   (`vMAJOR.MINOR.PATCH`) and create the GitHub Release. Today that means a
   second **Run workflow** on `main`. If `push: branches: [main]` is
   re-enabled, the merge itself starts that job. The same job attaches
   `bootstrap/install.sh`. A separate `release: published` workflow cannot
   do this — `GITHUB_TOKEN` is not allowed to start a second workflow after
   it creates the tag.
5. The tag triggers the build pipeline: the full test gate re-runs, the
   container image builds, gets scanned (Trivy) for known vulnerabilities,
   and — only if that passes — publishes to GitHub Container Registry under
   the new version tag. The attached script is what this one-liner fetches:

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

**Publishing a release does not deploy it anywhere.** Every tenant's deployment
is independent. In Phase 1 the operator adopts a new version by pointing the
bootstrap LXC at the new image tag (re-running the pinned install script, or
an equivalent pull). After Deploy, the same idea becomes an edit to that
tenant's Fleet repo — see the Bootstrap PRD and the Deploy stub. A GitHub
release landing is an announcement that a version exists and is available to
pull, not an instruction that anyone must pull it.

## If you're not a maintainer

You don't need to think about any of this to contribute — just follow
`CONTRIBUTING.md`'s commit/PR conventions. Everything above happens after your
PR merges, without any action on your part. If you are an agent, stop at the
feature/fix PR; never take a step from the table above that is marked
maintainer-only.
