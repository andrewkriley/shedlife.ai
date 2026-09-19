"""Idempotent install decision, per docs/spec/bootstrap.md.

The host-side script is bash (`bootstrap/install.sh`). This module is the
tested contract that script implements: reuse a healthy CT, otherwise create.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InstallState:
    ctid: int
    ct_ip: str
    image_ref: str
    health_ok: bool


def should_reuse(state: InstallState | None, live_health_ok: bool) -> bool:
    if state is None:
        return False
    return state.health_ok and live_health_ok and bool(state.ct_ip)


def parse_state(data: dict[str, Any] | None) -> InstallState | None:
    if not data:
        return None
    try:
        return InstallState(
            ctid=int(data["ctid"]),
            ct_ip=str(data["ct_ip"]),
            image_ref=str(data.get("image_ref") or ""),
            health_ok=bool((data.get("health") or {}).get("last_ok")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def render_url(ct_ip: str, port: int = 8080) -> str:
    return f"http://{ct_ip}:{port}"
