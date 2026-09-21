"""Version bumps must come from the manual release-please PR, not a handmade edit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "release_authority.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-authority.yml"


def _load():
    spec = importlib.util.spec_from_file_location("release_authority", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_feature_pr_without_release_files_is_allowed() -> None:
    gate = _load()
    ok, _ = gate.release_authority_ok(
        ["backend/src/app.py", "frontend/src/App.tsx"],
        head_ref="cursor/some-feature-8f92",
        author="cursor-agent",
    )
    assert ok is True


def test_handmade_changelog_edit_is_denied() -> None:
    gate = _load()
    ok, reason = gate.release_authority_ok(
        ["CHANGELOG.md", "README.md"],
        head_ref="cursor/bump-version-8f92",
        author="andrewkriley",
    )
    assert ok is False
    assert "release-please" in reason


def test_handmade_manifest_edit_is_denied() -> None:
    gate = _load()
    ok, _ = gate.release_authority_ok(
        [".release-please-manifest.json"],
        head_ref="fix/typo",
        author="github-actions[bot]",
    )
    assert ok is False


def test_nested_changelog_path_is_not_a_release_artifact() -> None:
    gate = _load()
    ok, _ = gate.release_authority_ok(
        ["docs/CHANGELOG.md"],
        head_ref="docs/notes",
        author="andrewkriley",
    )
    assert ok is True


def test_release_please_pr_from_the_bot_is_allowed() -> None:
    gate = _load()
    ok, _ = gate.release_authority_ok(
        ["CHANGELOG.md", ".release-please-manifest.json"],
        head_ref="release-please--branches--main--components--theshed",
        author="github-actions[bot]",
    )
    assert ok is True


def test_release_please_branch_from_a_human_is_denied() -> None:
    gate = _load()
    ok, _ = gate.release_authority_ok(
        ["CHANGELOG.md"],
        head_ref="release-please--branches--main--components--theshed",
        author="andrewkriley",
    )
    assert ok is False


def test_bot_author_on_a_feature_branch_is_denied() -> None:
    gate = _load()
    ok, _ = gate.release_authority_ok(
        [".release-please-manifest.json"],
        head_ref="cursor/fake-release-8f92",
        author="github-actions[bot]",
    )
    assert ok is False


def test_workflow_job_name_is_the_required_check() -> None:
    text = WORKFLOW.read_text()
    assert "name: release-please authority" in text
    assert "release_authority.py" in text
    assert "github.event.pull_request.user.login" in text
