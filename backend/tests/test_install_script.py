from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bootstrap" / "install.sh"
README = ROOT / "README.md"


def test_install_script_exists_and_is_thin() -> None:
    text = SCRIPT.read_text()
    assert SCRIPT.is_file()
    assert text.startswith("#!/usr/bin/env bash")
    assert "THESHED_REF" in text
    assert "/health" in text
    assert "install-state.yaml" in text
    assert "pct create" in text


def test_install_script_does_not_collect_operator_secrets() -> None:
    text = SCRIPT.read_text()
    assert "Does not collect an LLM API key" in text
    assert "read -p" not in text
    assert "ANTHROPIC_API_KEY" not in text
    assert "sk-ant" not in text


def test_readme_install_follows_the_latest_release() -> None:
    text = README.read_text()
    assert "releases/latest" in text
    assert "shedlife.ai/<tag>/bootstrap/install.sh" not in text
    assert "${tag}/bootstrap/install.sh" in text
