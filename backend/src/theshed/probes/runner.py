"""Probe dispatch, per docs/prd/bootstrap.md.

Minimums are implementation constants, not a design question:
4 vCPU / 16 GiB RAM / 100 GiB disk, NTP offset ≤ 5s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MIN_VCPU = 4
MIN_RAM_GB = 16
MIN_DISK_GB = 100
NTP_OFFSET_MAX_SECONDS = 5.0

PROBE_IDS = (
    "llm_key",
    "outbound_https",
    "proxmox_api",
    "proxmox_capacity",
    "bridge_exists",
    "storage_pool_exists",
    "ntp_ok",
    "ssh_key_installed",
    "adopted_endpoint",
    "domain_resolves",
)

SIDE_EFFECT_PROBES = frozenset({"ssh_key_installed"})


@dataclass
class ProbeResult:
    status: str  # pass | fail | warn | skip | error
    detail: str = ""


class ProbeHost(Protocol):
    def llm_key(self) -> ProbeResult: ...
    def outbound_https(self) -> ProbeResult: ...
    def proxmox_api(self) -> ProbeResult: ...
    def proxmox_capacity(self) -> ProbeResult: ...
    def bridge_exists(self) -> ProbeResult: ...
    def storage_pool_exists(self) -> ProbeResult: ...
    def ntp_ok(self) -> ProbeResult: ...
    def ssh_key_installed(self) -> ProbeResult: ...
    def adopted_endpoint(self) -> ProbeResult: ...
    def domain_resolves(self) -> ProbeResult: ...


def run_probe(probe_id: str, host: ProbeHost) -> ProbeResult:
    if probe_id not in PROBE_IDS:
        return ProbeResult("error", detail=f"unknown probe: {probe_id}")
    method = getattr(host, probe_id, None)
    if method is None:
        return ProbeResult("error", detail=f"host cannot run {probe_id}")
    try:
        return method()
    except Exception as exc:
        return ProbeResult("error", detail=str(exc))
