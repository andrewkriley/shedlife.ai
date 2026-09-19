"""In-memory debug ring for live troubleshooting.

Enabled by THESHED_DEBUG or a persisted local://debug/enabled toggle.
Never stores raw secrets — values that look like keys/passwords are redacted.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError, SecretsClient

DEBUG_SECRET = "local://debug/enabled"
DEBUG_ENV = "THESHED_DEBUG"
RING_SIZE = 500
# LXC/Proxmox console is bind-mounted at /host/console when compose can.
CONSOLE_PATHS = ("/host/console", "/dev/console")

_SECRET_KEYS = re.compile(
    r"(password|passwd|api[_-]?key|authorization|token|secret|credential)",
    re.IGNORECASE,
)
_SECRET_VALUES = re.compile(r"(sk-ant-[A-Za-z0-9_-]+|sk-[A-Za-z0-9]{12,})")

_lock = threading.Lock()
_events: deque[dict[str, Any]] = deque(maxlen=RING_SIZE)
_secrets: SecretsClient | None = None


def bind_secrets(secrets: SecretsClient | None) -> None:
    global _secrets
    _secrets = secrets


def reset_for_tests() -> None:
    with _lock:
        _events.clear()
    bind_secrets(None)


def is_enabled(environ: dict[str, str] | None = None) -> bool:
    if _secrets is not None:
        try:
            return _secrets.get(DEBUG_SECRET) == "1"
        except SecretNotFoundError:
            pass
    env = environ if environ is not None else os.environ
    return env.get(DEBUG_ENV, "").strip().lower() in {"1", "true", "yes"}


def set_enabled(enabled: bool) -> None:
    if isinstance(_secrets, LocalSecretsClient):
        _secrets.set(DEBUG_SECRET, "1" if enabled else "0")
        return
    os.environ[DEBUG_ENV] = "1" if enabled else "0"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if _SECRET_KEYS.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUES.sub("***", value)
    return value


def record(
    source: str,
    event: str,
    message: str,
    *,
    level: str = "info",
    detail: Any | None = None,
) -> dict[str, Any] | None:
    if not is_enabled():
        return None
    entry = {
        "at": datetime.now(UTC).isoformat(),
        "level": level,
        "source": source,
        "event": event,
        "message": redact(message),
        "detail": redact(detail),
    }
    with _lock:
        _events.append(entry)
    _write_console(format_console_line(entry))
    return entry


def format_console_line(entry: dict[str, Any]) -> str:
    line = (
        f"[debug] {entry['at']} {entry['level']} "
        f"{entry['source']}.{entry['event']}: {entry['message']}"
    )
    if entry.get("detail") is not None:
        line += f" {json.dumps(entry['detail'], default=str)}"
    return line


def _write_console(line: str) -> None:
    print(line, file=sys.stdout, flush=True)
    for path in CONSOLE_PATHS:
        try:
            with open(path, "a", encoding="utf-8", errors="replace") as console:
                console.write(line + "\n")
                console.flush()
        except OSError:
            continue


def snapshot() -> list[dict[str, Any]]:
    with _lock:
        return list(_events)
