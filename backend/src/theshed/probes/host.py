"""Default probe host. Network/Proxmox calls are injected so tests stay dry."""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from theshed.probes.runner import (
    MIN_DISK_GB,
    MIN_RAM_GB,
    MIN_VCPU,
    NTP_OFFSET_MAX_SECONDS,
    ProbeResult,
)


class DefaultProbeHost:
    def __init__(
        self,
        *,
        secrets: Any = None,
        foundations: Callable[[], dict[str, Any]] | None = None,
        http_get: Callable[[str, float], tuple[int, str]] | None = None,
        resolve: Callable[[str], list[str]] | None = None,
        clock_offset: Callable[[], float] | None = None,
        proxmox_facts: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._secrets = secrets
        self._foundations = foundations
        self._http_get = http_get or _http_get
        self._resolve = resolve or _resolve
        self._clock_offset = clock_offset
        self._proxmox_facts = proxmox_facts

    def bind(self, foundations: Callable[[], dict[str, Any]]) -> DefaultProbeHost:
        """Per-request host with the current foundations document."""
        return DefaultProbeHost(
            secrets=self._secrets,
            foundations=foundations,
            http_get=self._http_get,
            resolve=self._resolve,
            clock_offset=self._clock_offset,
            proxmox_facts=self._proxmox_facts,
        )

    def _doc(self) -> dict[str, Any]:
        return self._foundations() if self._foundations else {}

    def llm_key(self) -> ProbeResult:
        if self._secrets is None:
            return ProbeResult("fail", detail="no secrets client")
        try:
            self._secrets.get("local://providers/llm/api_key")
        except Exception as exc:  # noqa: BLE001 — any secrets miss is a probe fail
            return ProbeResult("fail", detail=str(exc))
        return ProbeResult("pass")

    def outbound_https(self) -> ProbeResult:
        try:
            status, _ = self._http_get("https://example.com", 5.0)
        except Exception as exc:  # noqa: BLE001 — injected HTTP can raise anything
            return ProbeResult("fail", detail=str(exc))
        if status >= 400:
            return ProbeResult("fail", detail=f"HTTP {status}")
        return ProbeResult("pass")

    def proxmox_api(self) -> ProbeResult:
        host = ((self._doc().get("proxmox") or {}).get("host") or "").strip()
        if not host:
            return ProbeResult("fail", detail="proxmox.host is empty")
        url = host if host.startswith("http") else f"https://{host}:8006"
        try:
            status, _ = self._http_get(url, 5.0)
        except Exception as exc:  # noqa: BLE001 — injected HTTP can raise anything
            return ProbeResult("fail", detail=str(exc))
        return ProbeResult("pass" if status < 500 else "fail", detail=f"HTTP {status}")

    def proxmox_capacity(self) -> ProbeResult:
        if self._proxmox_facts is None:
            return ProbeResult("warn", detail="capacity facts unavailable")
        facts = self._proxmox_facts()
        vcpu = int(facts.get("vcpu") or 0)
        ram = int(facts.get("ram_gb") or 0)
        disk = int(facts.get("disk_gb") or 0)
        if vcpu >= MIN_VCPU and ram >= MIN_RAM_GB and disk >= MIN_DISK_GB:
            return ProbeResult("pass")
        return ProbeResult(
            "warn",
            detail=f"{vcpu} vCPU / {ram} GiB / {disk} GiB; minimum {MIN_VCPU}/{MIN_RAM_GB}/{MIN_DISK_GB}",
        )

    def bridge_exists(self) -> ProbeResult:
        if self._proxmox_facts is None:
            return ProbeResult("warn", detail="cannot list bridges")
        wanted = (self._doc().get("network") or {}).get("bridge")
        bridges = self._proxmox_facts().get("bridges") or []
        if wanted in bridges:
            return ProbeResult("pass")
        return ProbeResult("fail", detail=f"{wanted} not in {bridges}")

    def storage_pool_exists(self) -> ProbeResult:
        if self._proxmox_facts is None:
            return ProbeResult("warn", detail="cannot list pools")
        wanted = (self._doc().get("storage") or {}).get("pool")
        pools = self._proxmox_facts().get("pools") or []
        if wanted in pools:
            return ProbeResult("pass")
        return ProbeResult("fail", detail=f"{wanted} not in {pools}")

    def ntp_ok(self) -> ProbeResult:
        offset = 0.0 if self._clock_offset is None else self._clock_offset()
        if abs(offset) <= NTP_OFFSET_MAX_SECONDS:
            return ProbeResult("pass")
        return ProbeResult("fail", detail=f"clock offset {offset}s")

    def ssh_key_installed(self) -> ProbeResult:
        fingerprint = (self._doc().get("proxmox") or {}).get("ssh_key_fingerprint")
        if fingerprint:
            return ProbeResult("pass")
        return ProbeResult("fail", detail="ssh key not installed")

    def adopted_endpoint(self) -> ProbeResult:
        intent = self._doc().get("intent") or {}
        urls: list[str] = []
        for entry in intent.values():
            mode = (entry or {}).get("mode")
            if mode in {"adopt", "brownfield"} and (entry or {}).get("url"):
                urls.append(str(entry["url"]))
        if not urls:
            return ProbeResult("skip")
        for url in urls:
            try:
                status, _ = self._http_get(url, 5.0)
            except Exception as exc:  # noqa: BLE001 — injected HTTP can raise anything
                return ProbeResult("fail", detail=f"{url}: {exc}")
            if status >= 500:
                return ProbeResult("fail", detail=f"{url}: HTTP {status}")
        return ProbeResult("pass")

    def domain_resolves(self) -> ProbeResult:
        names = (self._doc().get("domains") or {}).get("intended") or []
        if not names:
            return ProbeResult("skip")
        unresolved = [n for n in names if not self._resolve(str(n))]
        if unresolved:
            return ProbeResult("warn", detail=f"do not resolve yet: {unresolved}")
        return ProbeResult("pass")


def _http_get(url: str, timeout: float) -> tuple[int, str]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(response.status), ""
    except URLError as exc:
        raise RuntimeError(str(exc.reason if exc.reason else exc)) from exc


def _resolve(name: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(name, None)
    except socket.gaierror:
        return []
    return sorted({str(item[4][0]) for item in infos if item[4]})
