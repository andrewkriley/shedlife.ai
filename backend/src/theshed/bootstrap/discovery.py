"""Read-only discovery for bootstrap.intake.

These tools enumerate the host and adopted endpoints so the assistant can
propose known foundations keys. They never write the schema, never run a
fifth playbook, and never provision GitLab / Infisical / DNS / k3s.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ADOPT_MODES = frozenset({"adopt", "brownfield"})

DISCOVERY_TOOLS = (
    "list_proxmox_nodes",
    "list_bridges",
    "list_storage_pools",
    "proxmox_version",
    "discover_gitlab",
    "discover_infisical",
    "discover_dns",
    "discover_k3s",
)

HttpGet = Callable[[str, float], tuple[int, str]]
FactsFn = Callable[[], dict[str, Any]]
FoundationsFn = Callable[[], dict[str, Any]]


@dataclass
class DiscoveryResult:
    status: str  # found | skip | fail | error
    values: dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    provenance: str = "discovered"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "values": self.values,
            "detail": self.detail,
            "provenance": self.provenance,
        }


def run_discovery(name: str, host: DiscoveryHost) -> DiscoveryResult:
    if name not in DISCOVERY_TOOLS:
        return DiscoveryResult("error", detail=f"unknown discovery tool: {name}")
    method = getattr(host, name, None)
    if not callable(method):
        return DiscoveryResult("error", detail=f"host cannot run {name}")
    try:
        result = method()
    except Exception as exc:  # noqa: BLE001 — unexpected crash becomes an issue
        return DiscoveryResult("error", detail=str(exc))
    if not isinstance(result, DiscoveryResult):
        return DiscoveryResult("error", detail=f"host returned a non-result for {name}")
    return result


def host_for(probe_host: Any, doc: dict[str, Any]) -> DiscoveryHost:
    """Reuse the probe host's injected HTTP / Proxmox facts."""
    if isinstance(probe_host, DiscoveryHost):
        return DiscoveryHost(
            foundations=lambda: doc,
            http_get=probe_host._http_get,
            proxmox_facts=probe_host._proxmox_facts,
        )
    return DiscoveryHost(
        foundations=lambda: doc,
        http_get=getattr(probe_host, "_http_get", None),
        proxmox_facts=getattr(probe_host, "_proxmox_facts", None),
    )


class DiscoveryHost:
    def __init__(
        self,
        *,
        foundations: FoundationsFn | None = None,
        http_get: HttpGet | None = None,
        proxmox_facts: FactsFn | None = None,
    ) -> None:
        self._foundations = foundations
        self._http_get = http_get
        self._proxmox_facts = proxmox_facts

    def _doc(self) -> dict[str, Any]:
        return self._foundations() if self._foundations else {}

    def _facts(self) -> dict[str, Any] | None:
        if self._proxmox_facts is None:
            return None
        return self._proxmox_facts() or {}

    def list_proxmox_nodes(self) -> DiscoveryResult:
        facts = self._facts()
        if facts is None:
            return DiscoveryResult("skip", detail="proxmox facts unavailable")
        return DiscoveryResult("found", values={"nodes": list(facts.get("nodes") or [])})

    def list_bridges(self) -> DiscoveryResult:
        facts = self._facts()
        if facts is None:
            return DiscoveryResult("skip", detail="proxmox facts unavailable")
        return DiscoveryResult("found", values={"bridges": list(facts.get("bridges") or [])})

    def list_storage_pools(self) -> DiscoveryResult:
        facts = self._facts()
        if facts is None:
            return DiscoveryResult("skip", detail="proxmox facts unavailable")
        return DiscoveryResult("found", values={"pools": list(facts.get("pools") or [])})

    def proxmox_version(self) -> DiscoveryResult:
        facts = self._facts()
        if facts is None:
            return DiscoveryResult("skip", detail="proxmox facts unavailable")
        version = facts.get("version")
        if not version:
            return DiscoveryResult("fail", detail="version not reported")
        return DiscoveryResult("found", values={"version": str(version)})

    def discover_gitlab(self) -> DiscoveryResult:
        return self._discover_adopted("gitlab")

    def discover_infisical(self) -> DiscoveryResult:
        return self._discover_adopted("infisical")

    def discover_dns(self) -> DiscoveryResult:
        return self._discover_adopted("dns")

    def discover_k3s(self) -> DiscoveryResult:
        return self._discover_adopted("k3s", allow_kubeconfig_only=True)

    def _discover_adopted(
        self, key: str, *, allow_kubeconfig_only: bool = False
    ) -> DiscoveryResult:
        entry = (self._doc().get("intent") or {}).get(key) or {}
        mode = entry.get("mode")
        if mode not in ADOPT_MODES:
            return DiscoveryResult(
                "skip",
                detail=f"intent.{key}.mode is {mode or 'unset'}; discovery is for adopt/brownfield",
            )
        url = str(entry.get("url") or "").strip()
        if not url:
            if allow_kubeconfig_only and entry.get("kubeconfig_ref"):
                return DiscoveryResult(
                    "skip",
                    detail="k3s adopt uses kubeconfig_ref; no URL to probe",
                )
            return DiscoveryResult("fail", detail=f"intent.{key}.url is empty")
        if self._http_get is None:
            return DiscoveryResult("skip", detail="http client unavailable")
        try:
            status, _body = self._http_get(url, 5.0)
        except Exception as exc:  # noqa: BLE001 — injected HTTP can raise anything
            return DiscoveryResult("fail", detail=f"{url}: {exc}")
        if status >= 500:
            return DiscoveryResult(
                "fail", values={"http_status": status}, detail=f"HTTP {status}"
            )
        return DiscoveryResult(
            "found",
            values={"url": url, "http_status": status, "reachable": True},
            detail=f"HTTP {status}",
        )
