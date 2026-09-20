"""Galileo settings for the Settings surface.

Project, host (console URL), log stream, and API key are what the SDK
needs to send turn traces. The key is a secret; the others are stored
alongside it in the local store so they survive a restart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from theshed.observability.galileo import TurnTracer
from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError

GALILEO_API_KEY_REF = "local://observability/galileo_api_key"
GALILEO_HOST_REF = "local://observability/galileo_console_url"
GALILEO_PROJECT_REF = "local://observability/galileo_project"
GALILEO_LOG_STREAM_REF = "local://observability/galileo_log_stream"

DEFAULT_PROJECT = "the-shed"
DEFAULT_LOG_STREAM = "default"


@dataclass
class GalileoSettings:
    project: str
    host: str
    log_stream: str
    api_key_set: bool

    @property
    def configured(self) -> bool:
        return self.api_key_set


def _secret_or_env(secrets: Any, ref: str, env_keys: tuple[str, ...], default: str = "") -> str:
    if secrets is not None:
        try:
            value = secrets.get(ref)
            if isinstance(value, str) and value:
                return value
        except SecretNotFoundError:
            pass
    for key in env_keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return default


def read_galileo_settings(secrets: Any) -> GalileoSettings:
    api_key = _secret_or_env(secrets, GALILEO_API_KEY_REF, ("GALILEO_API_KEY",))
    return GalileoSettings(
        project=_secret_or_env(
            secrets,
            GALILEO_PROJECT_REF,
            ("GALILEO_PROJECT", "GALILEO_PROJECT_NAME"),
            DEFAULT_PROJECT,
        ),
        host=_secret_or_env(secrets, GALILEO_HOST_REF, ("GALILEO_CONSOLE_URL",)),
        log_stream=_secret_or_env(
            secrets, GALILEO_LOG_STREAM_REF, ("GALILEO_LOG_STREAM",), DEFAULT_LOG_STREAM
        ),
        api_key_set=bool(api_key),
    )


def write_galileo_settings(
    secrets: Any,
    *,
    project: str | None = None,
    host: str | None = None,
    log_stream: str | None = None,
    api_key: str | None = None,
) -> GalileoSettings:
    if isinstance(secrets, LocalSecretsClient):
        if project is not None:
            secrets.set(GALILEO_PROJECT_REF, project.strip())
        if host is not None:
            secrets.set(GALILEO_HOST_REF, host.strip())
        if log_stream is not None:
            secrets.set(GALILEO_LOG_STREAM_REF, log_stream.strip())
        if api_key is not None and api_key.strip():
            secrets.set(GALILEO_API_KEY_REF, api_key.strip())
    return read_galileo_settings(secrets)


def apply_galileo_runtime(app_state: Any, secrets: Any) -> GalileoSettings:
    """Push current settings into the process env and the tracer factory.

    The Galileo SDK reads GALILEO_* from the environment. A missing API key
    keeps the no-op tracer so a turn never fails because tracing is down.
    """
    settings = read_galileo_settings(secrets)
    api_key = _secret_or_env(secrets, GALILEO_API_KEY_REF, ("GALILEO_API_KEY",))
    if api_key:
        os.environ["GALILEO_API_KEY"] = api_key
    if settings.host:
        os.environ["GALILEO_CONSOLE_URL"] = settings.host
    os.environ["GALILEO_PROJECT"] = settings.project
    os.environ["GALILEO_LOG_STREAM"] = settings.log_stream
    project = settings.project
    stream = settings.log_stream
    if api_key:
        app_state.tracer_factory = lambda p=project, s=stream: TurnTracer.create(p, s)
    else:
        app_state.tracer_factory = lambda: TurnTracer(None)
    return settings
