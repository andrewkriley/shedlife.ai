"""Foundations document shape, per docs/spec/bootstrap.md."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1

KNOWN_TOP_LEVEL = frozenset(
    {"version", "tenant", "operator", "proxmox", "network", "storage", "domains", "intent", "probes"}
)

INTENT_KEYS = ("gitlab", "infisical", "dns", "k3s")


def empty_foundations() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "tenant": {"name": "", "slug": ""},
        "operator": {"email": ""},
        "proxmox": {"host": "", "node": "", "ssh_key_fingerprint": None},
        "network": {"bridge": "", "address": "", "gateway": "", "ntp": "inherit"},
        "storage": {"pool": ""},
        "domains": {"intended": []},
        "intent": {
            "gitlab": {"mode": "build"},
            "infisical": {"mode": "build"},
            "dns": {"mode": "greenfield"},
            "k3s": {"mode": "build"},
        },
        "probes": {},
    }


def merge_foundations(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge known sections. Unknown top-level keys are kept so
    validate_foundations can reject them."""
    merged = {**base, **{k: v for k, v in patch.items() if k != "probes"}}
    if "probes" in patch:
        current = dict(base.get("probes") or {})
        current.update(patch["probes"])
        merged["probes"] = current
    elif "probes" in base:
        merged["probes"] = dict(base["probes"])
    return merged
