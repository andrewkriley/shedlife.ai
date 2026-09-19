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


def test_readme_install_is_a_one_line_latest_release() -> None:
    text = README.read_text()
    assert (
        "curl -fsSL https://github.com/andrewkriley/shedlife.ai/releases/latest/download/install.sh | bash"
        in text
    )
    assert "tag=$(" not in text


def test_install_script_pins_ubuntu_26_04() -> None:
    text = SCRIPT.read_text()
    assert "debian-12-standard" not in text
    assert "ubuntu-26.04-standard" in text
    assert "ubuntu-[0-9]" not in text
    assert "sort -V" in text
    assert "pveam download local \"${name}\" >&2" in text
    assert 'volume="local:vztmpl/${name}"' in text
    assert "-gt 255" in text
