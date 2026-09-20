from theshed.debug import log as debug_log
from theshed.secrets.client import LocalSecretsClient


def setup_function() -> None:
    debug_log.reset_for_tests()


def test_record_is_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("THESHED_DEBUG", raising=False)
    assert debug_log.record("ui", "click", "Save") is None
    assert debug_log.snapshot() == []


def test_record_keeps_events_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    debug_log.record("provider", "connect", "Trying anthropic", detail={"api_key": "sk-ant-secret"})
    events = debug_log.snapshot()
    assert len(events) == 1
    assert events[0]["source"] == "provider"
    assert events[0]["event"] == "connect"
    assert events[0]["detail"]["api_key"] == "***"


def test_redacts_key_shaped_values(monkeypatch) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    debug_log.record("http", "error", "failed sk-ant-api03-abcdefghijk")
    assert "***" in debug_log.snapshot()[0]["message"]
    assert "sk-ant" not in debug_log.snapshot()[0]["message"]


def test_persisted_toggle_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    secrets = LocalSecretsClient()
    debug_log.bind_secrets(secrets)
    debug_log.set_enabled(False)
    assert debug_log.is_enabled() is False
    debug_log.set_enabled(True)
    assert debug_log.is_enabled() is True
    assert secrets.get("local://debug/enabled") == "1"


def test_record_prints_redacted_line_to_stdout(monkeypatch, capsys) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    debug_log.record(
        "ui",
        "click",
        "Save",
        detail={"password": "once-only", "path": "/settings"},
    )
    out = capsys.readouterr().out
    assert "[debug]" in out
    assert "ui.click" in out
    assert "Save" in out
    assert "once-only" not in out
    assert "***" in out


def test_record_does_not_print_when_disabled(monkeypatch, capsys) -> None:
    monkeypatch.delenv("THESHED_DEBUG", raising=False)
    debug_log.record("ui", "click", "Save")
    assert capsys.readouterr().out == ""


def test_record_also_writes_host_console(monkeypatch, tmp_path, capsys) -> None:
    console = tmp_path / "console"
    monkeypatch.setenv("THESHED_DEBUG", "1")
    monkeypatch.setattr(debug_log, "CONSOLE_PATHS", (str(console),))
    debug_log.record("http", "error", "boom")
    text = console.read_text()
    assert "[debug]" in text
    assert "http.error" in text
    assert "boom" in text
