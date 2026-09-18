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

import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
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
        "infisical://the-shed/observability/galileo_api_key": "GALILEO_THESHED_API",
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
