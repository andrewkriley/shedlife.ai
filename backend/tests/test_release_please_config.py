import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "release-please-config.json"
RELEASE_PLEASE = ROOT / ".github" / "workflows" / "release-please.yml"


def test_zero_x_releases_are_patch_granular() -> None:
    """Lots of small edits should not burn a minor each feat. See RELEASING.md."""
    cfg = json.loads(CONFIG.read_text())
    pkg = cfg["packages"]["."]
    assert pkg["bump-patch-for-minor-pre-major"] is True
    assert pkg["bump-minor-pre-major"] is True


def test_release_please_attaches_install_script_in_the_same_job() -> None:
    """GITHUB_TOKEN cannot start a second workflow after it creates a release."""
    text = RELEASE_PLEASE.read_text()
    assert "id: release" in text
    assert "steps.release.outputs.release_created" in text
    assert "steps.release.outputs.tag_name" in text
    assert "gh release upload" in text
    assert "bootstrap/install.sh" in text
