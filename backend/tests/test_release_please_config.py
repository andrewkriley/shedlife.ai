import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "release-please-config.json"


def test_zero_x_releases_are_patch_granular() -> None:
    """Lots of small edits should not burn a minor each feat. See RELEASING.md."""
    cfg = json.loads(CONFIG.read_text())
    pkg = cfg["packages"]["."]
    assert pkg["bump-patch-for-minor-pre-major"] is True
    assert pkg["bump-minor-pre-major"] is True
