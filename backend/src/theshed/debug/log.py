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
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any

from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError, SecretsClient

DEBUG_SECRET = "local://debug/enabled"
DEBUG_ENV = "THESHED_DEBUG"
RING_SIZE = 500
# LXC/Proxmox console: compose bind-mounts the CT tty1 and /dev/console.
CONSOLE_PATHS = ("/host/tty1", "/dev/tty1", "/host/console", "/dev/console")

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
        "at": datetime.now().astimezone().isoformat(),
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


def format_timezone_label(moment: datetime) -> str:
    """UTC, or UTC±offset, for a timezone-aware datetime."""
    offset = moment.utcoffset()
    if offset is None:
        moment = moment.astimezone()
        offset = moment.utcoffset() or timedelta(0)
    total_seconds = int(offset.total_seconds())
    if total_seconds == 0:
        return "UTC"
    sign = "+" if total_seconds > 0 else "-"
    total_minutes = abs(total_seconds) // 60
    hours, minutes = divmod(total_minutes, 60)
    if minutes:
        return f"UTC{sign}{hours:02d}:{minutes:02d}"
    return f"UTC{sign}{hours}"


def format_local_timestamp(value: str) -> str:
    """Clock time in the process timezone — the CT / host local time — with zone."""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    if moment.tzinfo is None:
        moment = moment.astimezone()
    local = moment.astimezone()
    clock = local.strftime("%Y-%m-%d %H:%M:%S")
    return f"{clock} {format_timezone_label(local)}"


def format_console_line(entry: dict[str, Any]) -> str:
    line = (
        f"[debug] {format_local_timestamp(str(entry['at']))} {entry['level']} "
        f"{entry['source']}.{entry['event']}: {entry['message']}"
    )
    if entry.get("detail") is not None:
        line += f" {json.dumps(entry['detail'], default=str)}"
    return line


def _write_console(line: str) -> None:
    print(line, file=sys.stdout, flush=True)
    payload = (line + "\n").encode("utf-8", errors="replace")
    flags = os.O_WRONLY | os.O_NOCTTY | os.O_CREAT | os.O_APPEND
    for path in CONSOLE_PATHS:
        fd = -1
        try:
            fd = os.open(path, flags, 0o644)
            os.write(fd, payload)
        except OSError:
            continue
        finally:
            if fd >= 0:
                os.close(fd)


def snapshot() -> list[dict[str, Any]]:
    with _lock:
        return list(_events)


def log_llm_start(vendor: str, model: str, *, tools: int = 0) -> float:
    """Record that a model call is about to leave the process."""
    record(
        "llm",
        "call",
        f"Calling {vendor} {model}",
        detail={"vendor": vendor, "model": model, "tools": tools},
    )
    return time.monotonic()


def log_llm_done(
    vendor: str,
    model: str,
    started: float,
    *,
    chars: int,
    tools: int,
    stop_reason: str,
) -> None:
    elapsed_ms = int((time.monotonic() - started) * 1000)
    record(
        "llm",
        "done",
        f"{vendor} {model} returned {chars} chars in {elapsed_ms}ms",
        detail={
            "vendor": vendor,
            "model": model,
            "chars": chars,
            "tools": tools,
            "stop_reason": stop_reason,
            "ms": elapsed_ms,
        },
    )


def log_llm_error(vendor: str, model: str, started: float, exc: BaseException) -> None:
    elapsed_ms = int((time.monotonic() - started) * 1000)
    record(
        "llm",
        "error",
        f"{vendor} {model} failed after {elapsed_ms}ms: {exc}",
        level="error",
        detail={
            "vendor": vendor,
            "model": model,
            "ms": elapsed_ms,
            "type": type(exc).__name__,
        },
    )
