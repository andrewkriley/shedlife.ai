"""Idempotent install decision, per docs/spec/bootstrap.md.

The host-side script is bash (`bootstrap/install.sh`). This module is the
tested contract that script implements: reuse a healthy CT, otherwise create.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Ubuntu 26.04 LTS is the current latest Proxmox `*-standard` template.
# Pin the series; still take the newest pveam build of that series.
PINNED_UBUNTU_VERSION = "26.04"
_UBUNTU_STANDARD = re.compile(
    rf"^ubuntu-{re.escape(PINNED_UBUNTU_VERSION)}-standard\S*$"
)
_OSTEMPLATE_MAX = 255
_PREFERRED_STORAGES = ("local-lvm", "local-zfs", "local")


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
    """Pinned ubuntu-<version>-standard filename from `pveam available` text."""
    best_name: str | None = None
    for raw in available_text.splitlines():
        fields = raw.split()
        if not fields:
            continue
        name = fields[1] if len(fields) >= 2 and fields[0] == "system" else fields[0]
        if _UBUNTU_STANDARD.match(name) is None:
            continue
        if best_name is None or name > best_name:
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


def parse_pvesm_status(status_text: str) -> list[str]:
    """Active storage names from `pvesm status --content rootdir` text."""
    names: list[str] = []
    for raw in status_text.splitlines():
        fields = raw.split()
        if len(fields) < 3 or fields[0].lower() == "name":
            continue
        name, status = fields[0], fields[2]
        if status == "active":
            names.append(name)
    return names


def select_rootfs_storage(status_text: str, requested: str | None = None) -> str:
    """Pick a storage that can hold a CT rootfs. Names are host-specific."""
    names = parse_pvesm_status(status_text)
    available = ", ".join(names) or "(none)"
    if requested:
        if requested in names:
            return requested
        raise ValueError(
            f"storage {requested!r} does not exist or cannot hold a CT rootfs. "
            f"Available: {available}"
        )
    for candidate in _PREFERRED_STORAGES:
        if candidate in names:
            return candidate
    if names:
        return names[0]
    raise ValueError(
        "no active Proxmox storage with content rootdir. "
        "Enable rootdir on a storage, or set THESHED_STORAGE."
    )
