from types import SimpleNamespace

import pytest

from theshed.observability.galileo import TurnTracer
from theshed.secrets.client import LocalSecretsClient
from theshed.settings.galileo import (
    DEFAULT_LOG_STREAM,
    DEFAULT_PROJECT,
    GALILEO_API_KEY_REF,
    GALILEO_HOST_REF,
    GALILEO_LOG_STREAM_REF,
    GALILEO_PROJECT_REF,
    apply_galileo_runtime,
    read_galileo_settings,
    write_galileo_settings,
)


def test_read_galileo_settings_uses_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GALILEO_API_KEY", raising=False)
    monkeypatch.delenv("GALILEO_CONSOLE_URL", raising=False)
    monkeypatch.delenv("GALILEO_PROJECT", raising=False)
    monkeypatch.delenv("GALILEO_PROJECT_NAME", raising=False)
    monkeypatch.delenv("GALILEO_LOG_STREAM", raising=False)
    settings = read_galileo_settings(LocalSecretsClient())
    assert settings.project == DEFAULT_PROJECT
    assert settings.log_stream == DEFAULT_LOG_STREAM
    assert settings.host == ""
    assert settings.api_key_set is False
    assert settings.configured is False


def test_write_galileo_settings_persists_and_does_not_echo_the_key() -> None:
    secrets = LocalSecretsClient()
    settings = write_galileo_settings(
        secrets,
        project="shed-lab",
        host="https://galileo.example.test",
        log_stream="bootstrap",
        api_key="galileo-secret",
    )
    assert settings.project == "shed-lab"
    assert settings.host == "https://galileo.example.test"
    assert settings.log_stream == "bootstrap"
    assert settings.api_key_set is True
    assert secrets.get(GALILEO_PROJECT_REF) == "shed-lab"
    assert secrets.get(GALILEO_HOST_REF) == "https://galileo.example.test"
    assert secrets.get(GALILEO_LOG_STREAM_REF) == "bootstrap"
    assert secrets.get(GALILEO_API_KEY_REF) == "galileo-secret"


def test_write_without_api_key_keeps_the_existing_key() -> None:
    secrets = LocalSecretsClient()
    write_galileo_settings(secrets, api_key="galileo-secret", project="a")
    settings = write_galileo_settings(secrets, project="b", api_key="")
    assert settings.project == "b"
    assert secrets.get(GALILEO_API_KEY_REF) == "galileo-secret"


def test_apply_galileo_runtime_enables_the_tracer_when_a_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GALILEO_API_KEY", "")
    monkeypatch.setenv("GALILEO_CONSOLE_URL", "")
    monkeypatch.setenv("GALILEO_PROJECT", "")
    monkeypatch.setenv("GALILEO_LOG_STREAM", "")
    secrets = LocalSecretsClient()
    write_galileo_settings(secrets, project="shed-lab", log_stream="live", api_key="galileo-secret")
    state = SimpleNamespace()
    settings = apply_galileo_runtime(state, secrets)
    assert settings.configured is True
    tracer = state.tracer_factory()
    assert isinstance(tracer, TurnTracer)
    assert tracer._project == "shed-lab"
    assert tracer._log_stream == "live"


def test_apply_galileo_runtime_is_noop_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GALILEO_API_KEY", raising=False)
    monkeypatch.delenv("GALILEO_CONSOLE_URL", raising=False)
    monkeypatch.delenv("GALILEO_PROJECT", raising=False)
    monkeypatch.delenv("GALILEO_LOG_STREAM", raising=False)
    state = SimpleNamespace()
    apply_galileo_runtime(state, LocalSecretsClient())
    tracer = state.tracer_factory()
    assert isinstance(tracer, TurnTracer)
    assert tracer._project is None
