"""Shed-themed hostname proposals for collect-foundations.

Labels are devices you would find in a workshop shed — tools, electronics,
and test gear — used as the left-most hostname label. shedlife.ai is never
a default zone. The assistant offers these; it does not write the schema.
"""

from __future__ import annotations

from collections.abc import Sequence

from theshed.foundations.validate import HOSTNAME_RE

SHED_HOSTNAME_LABELS = (
    "bench",
    "vise",
    "lathe",
    "mill",
    "press",
    "solder",
    "iron",
    "flux",
    "scope",
    "meter",
    "probe",
    "drill",
    "rasp",
    "plane",
    "chisel",
    "clamp",
    "anvil",
    "wrench",
    "socket",
    "sander",
    "jointer",
    "torch",
    "breadboard",
    "jumper",
    "header",
    "crimper",
    "tweezers",
    "supply",
    "analyzer",
    "radio",
    "tuner",
    "amp",
    "rework",
    "caliper",
    "square",
    "level",
    "worklight",
    "pegboard",
    "router",
)

DEFAULT_COUNT = 3
MAX_COUNT = 8


def _first_label(name: str) -> str:
    return name.strip().rstrip(".").split(".")[0].lower()


def propose_hostnames(
    *,
    count: int = DEFAULT_COUNT,
    used: Sequence[str] = (),
    base: str | None = None,
) -> list[str]:
    n = max(0, min(int(count), MAX_COUNT))
    taken = {_first_label(item) for item in used if item}
    labels = [label for label in SHED_HOSTNAME_LABELS if label not in taken]
    zone = (base or "").strip().rstrip(".").lower()
    if zone:
        if not HOSTNAME_RE.fullmatch(zone):
            raise ValueError("base must be a hostname")
        already = {item.strip().rstrip(".").lower() for item in used if item}
        names = [f"{label}.{zone}" for label in labels if f"{label}.{zone}" not in already]
    else:
        names = labels
    return names[:n]
