from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from starlette.responses import PlainTextResponse

from theshed.debug import log as debug_log
from theshed.debug.middleware import DebugHttpMiddleware
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


def test_record_stores_a_system_local_timestamp(monkeypatch) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    entry = debug_log.record("ui", "click", "Save")
    assert entry is not None
    recorded = datetime.fromisoformat(entry["at"])
    assert recorded.tzinfo is not None
    assert recorded.utcoffset() == datetime.now().astimezone().utcoffset()


def test_timezone_label_for_utc() -> None:
    moment = datetime(2026, 9, 20, 0, 0, tzinfo=UTC)
    assert debug_log.format_timezone_label(moment) == "UTC"


def test_timezone_label_for_positive_offset() -> None:
    moment = datetime(2026, 9, 20, 10, 0, tzinfo=timezone(timedelta(hours=10)))
    assert debug_log.format_timezone_label(moment) == "UTC+10"


def test_timezone_label_for_negative_offset_with_minutes() -> None:
    moment = datetime(2026, 9, 20, 10, 0, tzinfo=timezone(timedelta(hours=-5, minutes=-30)))
    assert debug_log.format_timezone_label(moment) == "UTC-05:30"


def test_console_line_shows_system_local_clock_time_with_timezone() -> None:
    entry = {
        "at": "2026-09-20T00:00:00+00:00",
        "level": "info",
        "source": "ui",
        "event": "click",
        "message": "Save",
        "detail": None,
    }
    stamp = debug_log.format_local_timestamp(entry["at"])
    line = debug_log.format_console_line(entry)
    assert stamp in line
    assert "UTC" in stamp
    assert "T00:00:00" not in line
    local = datetime.fromisoformat(entry["at"]).astimezone()
    assert local.strftime("%Y-%m-%d %H:%M:%S") in stamp
    assert stamp.endswith(debug_log.format_timezone_label(local))


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


def test_console_paths_include_ct_tty1() -> None:
    assert "/host/tty1" in debug_log.CONSOLE_PATHS
    assert "/dev/tty1" in debug_log.CONSOLE_PATHS


def test_compose_bind_mounts_ct_tty1() -> None:
    compose = Path(__file__).resolve().parents[2] / "bootstrap" / "docker-compose.yml"
    text = compose.read_text()
    assert "/dev/tty1:/host/tty1" in text


def test_log_llm_helpers_record_call_and_done(monkeypatch) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    started = debug_log.log_llm_start("openai", "gpt-5.4", tools=1)
    debug_log.log_llm_done(
        "openai", "gpt-5.4", started, chars=12, tools=0, stop_reason="stop"
    )
    events = debug_log.snapshot()
    assert [item["source"] for item in events] == ["llm", "llm"]
    assert events[0]["event"] == "call"
    assert "gpt-5.4" in events[0]["message"]
    assert events[1]["event"] == "done"
    assert events[1]["detail"]["chars"] == 12


@pytest.mark.asyncio
async def test_http_middleware_records_start_before_the_response(
    monkeypatch,
) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    seen_start = False

    async def app(scope, receive, send):
        nonlocal seen_start
        events = debug_log.snapshot()
        seen_start = any(item["event"] == "start" and "/turns" in item["message"] for item in events)
        response = PlainTextResponse("ok")
        await response(scope, receive, send)

    middleware = DebugHttpMiddleware(app)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/turns",
        "raw_path": b"/turns",
        "query_string": b"",
        "headers": [],
        "client": ("test", 123),
        "server": ("test", 80),
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await middleware(scope, receive, send)
    assert seen_start is True
    assert any(item["event"] == "request" for item in debug_log.snapshot())


def test_log_llm_error_records_the_failure(monkeypatch) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    started = debug_log.log_llm_start("openai", "gpt-5.4")
    debug_log.log_llm_error("openai", "gpt-5.4", started, RuntimeError("timeout"))
    events = debug_log.snapshot()
    assert events[-1]["event"] == "error"
    assert events[-1]["level"] == "error"
    assert "timeout" in events[-1]["message"]


def test_debug_dock_css_is_in_page_flow_not_fixed() -> None:
    css_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "index.css"
    css = css_path.read_text()
    dock = css[css.index(".debug-dock {") : css.index(".debug-dock__bar")]
    shell = css[css.index(".app-shell {") : css.index(".app-header {")]
    assert "position: static" in dock
    assert "grid-column: 1 / -1" in dock
    assert "position: fixed" not in dock
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in shell
    assert "display: contents" in shell
    assert ".workspace--hidden" in shell
    assert "padding-bottom: 56px" not in css
