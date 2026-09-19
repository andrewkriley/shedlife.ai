"""Idempotent install decision, per docs/spec/bootstrap.md.

The host-side script is bash (`bootstrap/install.sh`). This module is the
tested contract that script implements: reuse a healthy CT, otherwise create.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_UBUNTU_STANDARD = re.compile(r"^ubuntu-(\d+)\.(\d+)-standard\S*$")
_OSTEMPLATE_MAX = 255


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


def select_os_template(available_text: str) -> str | None:
    """Latest ubuntu-*-standard filename from `pveam available` text."""
    best_name: str | None = None
    best_key: tuple[int, int, str] | None = None
    for raw in available_text.splitlines():
        fields = raw.split()
        if not fields:
            continue
        name = fields[1] if len(fields) >= 2 and fields[0] == "system" else fields[0]
        match = _UBUNTU_STANDARD.match(name)
        if match is None:
            continue
        key = (int(match.group(1)), int(match.group(2)), name)
        if best_key is None or key > best_key:
            best_key = key
            best_name = name
    return best_name


def ostemplate_volume(template_name: str, storage: str = "local") -> str:
    """Volume id for `pct create`. PVE rejects ostemplate values over 255 chars."""
    volume = f"{storage}:vztmpl/{template_name}"
    if len(volume) > _OSTEMPLATE_MAX:
        raise ValueError(
            f"ostemplate must be at most {_OSTEMPLATE_MAX} characters "
            "(pveam download output must not be captured)"
        )
    return volume
