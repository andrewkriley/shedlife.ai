"""Secrets client, per docs/spec/secrets-management.md.

Reference format: infisical://<project>/<path...>/<secret_name>

SecretsClient owns a short in-memory TTL cache so a rotated secret is picked
up without a restart, and a call-scoped fetch isn't paying a network round
trip on every single use. EnvVarSecretsClient is the dev-mode implementation
(see its docstring) — the real Infisical-backed client implements the same
ABC, so swapping one for the other is a constructor change, not a call-site
change.
"""

from __future__ import annotations

import json
import os
import stat
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar


class SecretNotFoundError(KeyError):
    """Raised when a reference has no resolvable value."""


class SecretsClient(ABC):
    def __init__(
        self,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._cache: dict[str, tuple[str, float]] = {}

    def get(self, reference: str) -> str:
        cached = self._cache.get(reference)
        if cached is not None:
            value, expires_at = cached
            if self._clock() < expires_at:
                return value
        value = self._fetch(reference)
        self._cache[reference] = (value, self._clock() + self._ttl_seconds)
        return value

    @abstractmethod
    def _fetch(self, reference: str) -> str:
        """Fetch a fresh value for `reference`, bypassing the cache.
        Raise SecretNotFoundError if it can't be resolved."""


class EnvVarSecretsClient(SecretsClient):
    """Dev-mode only. Resolves each reference against an explicit mapping to
    an environment variable name, rather than deriving one mechanically —
    real credentials in practice don't always follow a clean, derivable
    naming pattern (see GALILEO_THESHED_API below), and an explicit mapping
    stays correct without forcing a rename of an existing credential.

    Not the production path: see docs/spec/secrets-management.md,
    "Secret zero's runtime home" for the real Kubernetes-Secret + live
    Infisical mechanism this stands in for during local development.
    """

    DEFAULT_MAPPING: ClassVar[dict[str, str]] = {
        "infisical://the-shed/providers/anthropic/api_key": "ANTHROPIC_API_KEY",
        "infisical://the-shed/providers/openai/api_key": "OPENAI_API_KEY",
        "infisical://the-shed/observability/galileo_api_key": "GALILEO_API_KEY",
        "infisical://the-shed/observability/galileo_console_url": "GALILEO_URL",
        "infisical://the-shed/mcp/unifi_bearer_token": "UNFI_MCP_BEARER_TOKEN",
        "infisical://the-shed/mcp/unifi_url": "UNFI_MCP_URL",
    }

    def __init__(
        self,
        mapping: dict[str, str] | None = None,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        env: dict[str, str] | None = None,
    ) -> None:
        super().__init__(ttl_seconds=ttl_seconds, clock=clock)
        self._mapping = dict(self.DEFAULT_MAPPING) if mapping is None else mapping
        self._env = os.environ if env is None else env

    def _fetch(self, reference: str) -> str:
        env_var = self._mapping.get(reference)
        if env_var is None:
            raise SecretNotFoundError(f"No env var mapping for {reference!r}")
        value = self._env.get(env_var)
        if not value:
            raise SecretNotFoundError(f"{env_var} is not set (for {reference!r})")
        return value


LOCAL_SCHEME = "local://"


class LocalSecretsClient(SecretsClient):
    """Bootstrap-profile secret-zero. Values live in memory and, when a path
    is given, a 0600 JSON file on the LXC. References must be local://.
    See docs/spec/secrets-management.md and docs/spec/bootstrap.md."""

    def __init__(
        self,
        store: dict[str, str] | None = None,
        path: Path | str | None = None,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(ttl_seconds=ttl_seconds, clock=clock)
        self._path = Path(path) if path is not None else None
        self._store = dict(store or {})
        if self._path is not None and self._path.exists():
            loaded = json.loads(self._path.read_text())
            if isinstance(loaded, dict):
                self._store.update({str(k): str(v) for k, v in loaded.items()})

    def set(self, reference: str, value: str) -> None:
        if not reference.startswith(LOCAL_SCHEME):
            raise ValueError(f"LocalSecretsClient only stores {LOCAL_SCHEME} references")
        self._store[reference] = value
        self._cache.pop(reference, None)
        self._persist()

    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._store, indent=2, sort_keys=True))
        tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
        tmp.replace(self._path)
        self._path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def _fetch(self, reference: str) -> str:
        value = self._store.get(reference)
        if not value:
            raise SecretNotFoundError(f"No local secret for {reference!r}")
        return value
