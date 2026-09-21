"""Talk to a Proxmox API for onboarding discovery.

LAN nodes almost always present a self-signed TLS cert, so these calls
skip certificate verification. They never log the token.
"""

from __future__ import annotations

import json
import ssl
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HttpGet = Callable[..., tuple[int, str]]


def proxmox_base_url(host: str) -> str:
    host = host.strip()
    if not host:
        return ""
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"https://{host}:8006"


def unverified_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def proxmox_http_get(
    url: str, timeout: float, headers: dict[str, str] | None = None
) -> tuple[int, str]:
    request = Request(url, method="GET", headers=headers or {})
    try:
        with urlopen(request, timeout=timeout, context=unverified_ssl_context()) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), body
    except URLError as exc:
        raise RuntimeError(str(exc.reason if exc.reason else exc)) from exc


def _call(
    http_get: HttpGet, url: str, timeout: float, headers: dict[str, str] | None = None
) -> tuple[int, str]:
    try:
        return http_get(url, timeout, headers)
    except TypeError:
        return http_get(url, timeout)


def probe_proxmox_reachable(host: str, *, http_get: HttpGet | None = None) -> tuple[bool, str]:
    base = proxmox_base_url(host)
    if not base:
        return False, "proxmox.host is empty"
    getter = http_get or proxmox_http_get
    url = f"{base}/api2/json/version"
    try:
        status, _body = _call(getter, url, 5.0)
    except Exception as exc:  # noqa: BLE001 — transport failure is a reachability miss
        return False, str(exc)
    if status == 0:
        return False, "no response"
    return True, f"HTTP {status}"


def fetch_proxmox_inventory(
    host: str,
    token: str,
    *,
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    base = proxmox_base_url(host)
    if not base:
        raise ValueError("proxmox.host is empty")
    if not (token or "").strip():
        raise ValueError("proxmox API token is not set")
    getter = http_get or proxmox_http_get
    headers = {"Authorization": f"PVEAPIToken={token.strip()}"}

    def get_data(path: str) -> Any:
        status, body = _call(getter, f"{base}{path}", 8.0, headers)
        if status in {401, 403}:
            raise PermissionError("proxmox API token was rejected")
        if status >= 500 or status == 0:
            raise RuntimeError(f"HTTP {status}")
        if not body:
            return {}
        payload = json.loads(body)
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    version_data = get_data("/api2/json/version") or {}
    version = ""
    if isinstance(version_data, dict):
        version = str(version_data.get("version") or "")
    nodes_data = get_data("/api2/json/nodes") or []
    nodes: list[str] = []
    vcpu = 0
    ram_gb = 0
    disk_gb = 0
    if isinstance(nodes_data, list):
        for item in nodes_data:
            if not isinstance(item, dict):
                continue
            name = item.get("node") or item.get("name")
            if name:
                nodes.append(str(name))
            vcpu = max(vcpu, int(item.get("maxcpu") or 0))
            ram = int(item.get("maxmem") or 0)
            if ram > 0:
                ram_gb = max(ram_gb, ram // (1024**3))
            disk = int(item.get("maxdisk") or 0)
            if disk > 0:
                disk_gb = max(disk_gb, disk // (1024**3))
    node = nodes[0] if nodes else None
    bridges: list[str] = []
    if node:
        net = get_data(f"/api2/json/nodes/{node}/network") or []
        if isinstance(net, list):
            for item in net:
                if not isinstance(item, dict):
                    continue
                iface = str(item.get("iface") or "")
                if iface and iface not in bridges and (
                    item.get("type") == "bridge" or iface.startswith("vmbr")
                ):
                    bridges.append(iface)
    storage = get_data("/api2/json/storage") or []
    pools: list[str] = []
    if isinstance(storage, list):
        for item in storage:
            if isinstance(item, dict) and item.get("storage"):
                name = str(item["storage"])
                if name not in pools:
                    pools.append(name)
    return {
        "version": version,
        "nodes": nodes,
        "bridges": bridges,
        "pools": pools,
        "vcpu": vcpu,
        "ram_gb": ram_gb,
        "disk_gb": disk_gb,
    }
