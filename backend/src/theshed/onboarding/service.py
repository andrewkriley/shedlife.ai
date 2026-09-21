"""Deterministic onboarding steps. The wizard is a UI over collect / probe."""

from __future__ import annotations

import ipaddress
from typing import Any

from theshed.bootstrap.proxmox import fetch_proxmox_inventory, probe_proxmox_reachable
from theshed.foundations.schema import INTENT_KEYS, PROXMOX_API_TOKEN_REF, empty_foundations
from theshed.foundations.tokens import (
    IncompleteProxmoxToken,
    persist_proxmox_api_token,
    present_foundations,
)
from theshed.foundations.validate import SLUG_RE
from theshed.probes.host import DefaultProbeHost
from theshed.probes.runner import ProbeResult, run_probe
from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError
from theshed.setup.providers import validate_api_key

SUMMARY_PROBES = (
    "llm_key",
    "outbound_https",
    "proxmox_api",
    "proxmox_capacity",
    "bridge_exists",
    "storage_pool_exists",
    "ntp_ok",
    "adopted_endpoint",
)

REQUIRED_SUMMARY = frozenset({"tenant", "llm_key", "proxmox_api"})

ADOPT_MODES = {"gitlab": "adopt", "infisical": "adopt", "dns": "brownfield", "k3s": "adopt"}


class IncompleteAdopt(ValueError):
    def __init__(self) -> None:
        super().__init__("Add at least one service URL to adopt")


class OnboardingError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("onboarding step failed")
        self.errors = errors


def _secret_text(secrets: Any, ref: str) -> str | None:
    if secrets is None:
        return None
    getter = getattr(secrets, "get", None)
    if getter is None:
        return None
    try:
        value = getter(ref)
    except SecretNotFoundError:
        return None
    except Exception:  # noqa: BLE001 — missing/broken store is "unset"
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def has_llm_key(secrets: Any) -> bool:
    return bool(_secret_text(secrets, "local://providers/llm/api_key"))


def llm_vendor(secrets: Any) -> str | None:
    return _secret_text(secrets, "local://providers/llm/vendor")


def onboarding_needed(document: dict[str, Any], secrets: Any) -> bool:
    presented = present_foundations(document, secrets)
    tenant = presented.get("tenant") or {}
    proxmox = presented.get("proxmox") or {}
    has_tenant = bool((tenant.get("name") or "").strip() and (tenant.get("slug") or "").strip())
    has_host = bool((proxmox.get("host") or "").strip())
    has_token = bool(proxmox.get("api_token_set"))
    return not (has_tenant and has_host and has_token and has_llm_key(secrets))


def intent_mode(document: dict[str, Any]) -> str:
    intent = document.get("intent") or {}
    for name in INTENT_KEYS:
        mode = ((intent.get(name) or {}).get("mode") or "").strip()
        if mode in {"adopt", "brownfield"}:
            return "adopt"
    return "build"


def intent_from_choice(mode: str, urls: dict[str, str] | None = None) -> dict[str, Any]:
    choice = (mode or "").strip().lower()
    if choice not in {"build", "adopt"}:
        raise OnboardingError({"intent.mode": "must be build or adopt"})
    intent: dict[str, Any] = dict(empty_foundations()["intent"])
    if choice == "build":
        return intent
    provided = {
        key: (value or "").strip()
        for key, value in (urls or {}).items()
        if key in INTENT_KEYS and (value or "").strip()
    }
    if not provided:
        raise IncompleteAdopt()
    for key, url in provided.items():
        intent[key] = {"mode": ADOPT_MODES[key], "url": url}
    return intent


def discovered_defaults(document: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    """Fill empty node / bridge / CIDR / gateway / pool. Never overwrite a set value."""
    patch: dict[str, Any] = {}
    proxmox = dict(document.get("proxmox") or {})
    network = dict(document.get("network") or {})
    storage = dict(document.get("storage") or {})
    nodes = [str(n) for n in (facts.get("nodes") or []) if n]
    bridges = [str(b) for b in (facts.get("bridges") or []) if b]
    pools = [str(p) for p in (facts.get("pools") or []) if p]
    networks = facts.get("networks") if isinstance(facts.get("networks"), dict) else {}
    if not (proxmox.get("node") or "").strip() and nodes:
        proxmox["node"] = nodes[0]
        patch["proxmox"] = proxmox
    if not (network.get("bridge") or "").strip() and bridges:
        network["bridge"] = "vmbr0" if "vmbr0" in bridges else bridges[0]
        patch["network"] = network
    bridge = (network.get("bridge") or "").strip()
    chosen = networks.get(bridge) if isinstance(networks.get(bridge), dict) else {}
    address = (facts.get("address") or chosen.get("address") or "").strip()
    gateway = (facts.get("gateway") or chosen.get("gateway") or "").strip()
    if not (network.get("address") or "").strip() and address:
        network["address"] = address
        patch["network"] = network
    if not (network.get("gateway") or "").strip() and gateway:
        network["gateway"] = gateway
        patch["network"] = network
    if not (storage.get("pool") or "").strip() and pools:
        storage["pool"] = "local-lvm" if "local-lvm" in pools else pools[0]
        patch["storage"] = storage
    return patch


def apply_network(
    document: dict[str, Any],
    *,
    bridge: str | None = None,
    address: str | None = None,
    gateway: str | None = None,
    pool: str | None = None,
) -> dict[str, Any]:
    errors: dict[str, str] = {}
    cleaned_address = (address or "").strip()
    cleaned_gateway = (gateway or "").strip()
    if cleaned_address:
        try:
            ipaddress.ip_network(cleaned_address, strict=False)
        except ValueError:
            errors["network.address"] = "must be CIDR (address/prefix)"
    if cleaned_gateway:
        try:
            ipaddress.ip_address(cleaned_gateway)
        except ValueError:
            errors["network.gateway"] = "must be an IP address"
    if errors:
        raise OnboardingError(errors)
    updated = dict(document)
    network = dict(updated.get("network") or {})
    if bridge is not None:
        network["bridge"] = bridge.strip()
    if address is not None:
        network["address"] = cleaned_address
    if gateway is not None:
        network["gateway"] = cleaned_gateway
    updated["network"] = network
    if pool is not None:
        storage = dict(updated.get("storage") or {})
        storage["pool"] = pool.strip()
        updated["storage"] = storage
    return updated


def apply_discovered_defaults(document: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    patch = discovered_defaults(document, facts)
    updated = dict(document)
    if "proxmox" in patch:
        updated["proxmox"] = {**(document.get("proxmox") or {}), **patch["proxmox"]}
    if "network" in patch:
        updated["network"] = {**(document.get("network") or {}), **patch["network"]}
    if "storage" in patch:
        updated["storage"] = {**(document.get("storage") or {}), **patch["storage"]}
    return updated


def apply_proxmox_host(document: dict[str, Any], host: str) -> dict[str, Any]:
    cleaned = (host or "").strip()
    if not cleaned:
        raise OnboardingError({"proxmox.host": "required"})
    updated = dict(document)
    proxmox = dict(updated.get("proxmox") or {})
    proxmox["host"] = cleaned
    updated["proxmox"] = proxmox
    return updated


def apply_tenant(document: dict[str, Any], name: str, slug: str) -> dict[str, Any]:
    errors: dict[str, str] = {}
    cleaned_name = (name or "").strip()
    cleaned_slug = (slug or "").strip()
    if not cleaned_name:
        errors["tenant.name"] = "required"
    if not cleaned_slug:
        errors["tenant.slug"] = "required"
    elif not SLUG_RE.fullmatch(cleaned_slug):
        errors["tenant.slug"] = "must match [a-z0-9-]+"
    if errors:
        raise OnboardingError(errors)
    updated = dict(document)
    updated["tenant"] = {"name": cleaned_name, "slug": cleaned_slug}
    return updated


def check_host_reachable(host: str, http_get: Any = None) -> None:
    ok, detail = probe_proxmox_reachable(host, http_get=http_get)
    if not ok:
        raise OnboardingError({"proxmox.host": detail or "Proxmox API is not reachable"})


def save_proxmox_token(
    document: dict[str, Any],
    secrets: Any,
    *,
    api_token_id: str | None = None,
    api_token_secret: str | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    token_id = (api_token_id or "").strip()
    token_secret = (api_token_secret or "").strip()
    combined = (api_token or "").strip()
    if not token_id and not token_secret and not combined:
        presented = present_foundations(document, secrets)
        if presented.get("proxmox", {}).get("api_token_set"):
            return persist_proxmox_api_token(document, secrets)
        if _secret_text(secrets, PROXMOX_API_TOKEN_REF):
            updated = dict(document)
            proxmox = dict(updated.get("proxmox") or {})
            proxmox["api_token_ref"] = PROXMOX_API_TOKEN_REF
            updated["proxmox"] = proxmox
            return persist_proxmox_api_token(updated, secrets)
        raise IncompleteProxmoxToken(
            {
                "proxmox.api_token_id": "required",
                "proxmox.api_token_secret": "required",
            }
        )
    patched = dict(document)
    proxmox = dict(patched.get("proxmox") or {})
    if combined:
        proxmox["api_token"] = combined
    else:
        proxmox["api_token_id"] = token_id
        proxmox["api_token_secret"] = token_secret
    patched["proxmox"] = proxmox
    return persist_proxmox_api_token(patched, secrets)


def save_provider(
    secrets: Any,
    provider: str,
    api_key: str,
    *,
    live_check: Any = None,
    configure: Any = None,
) -> str:
    vendor = (provider or "").strip()
    key = (api_key or "").strip()
    if not key:
        saved = _secret_text(secrets, "local://providers/llm/api_key")
        saved_vendor = llm_vendor(secrets) or vendor
        if saved and saved_vendor:
            validate_api_key(saved_vendor, saved, live_check=live_check)
            if configure is not None:
                configure(saved_vendor, saved)
            return saved_vendor
        raise OnboardingError({"provider.api_key": "required"})
    validate_api_key(vendor, key, live_check=live_check)
    if isinstance(secrets, LocalSecretsClient):
        secrets.set("local://providers/llm/vendor", vendor)
        secrets.set("local://providers/llm/api_key", key)
    if configure is not None:
        configure(vendor, key)
    return vendor


def discover_and_fill(
    document: dict[str, Any],
    secrets: Any,
    *,
    http_get: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    host = ((document.get("proxmox") or {}).get("host") or "").strip()
    token = _secret_text(secrets, PROXMOX_API_TOKEN_REF) or ""
    facts = fetch_proxmox_inventory(host, token, http_get=http_get)
    filled = apply_discovered_defaults(document, facts)
    return filled, facts


def bind_probe_host(template: Any, document: dict[str, Any], secrets: Any, facts: dict[str, Any] | None) -> Any:
    if isinstance(template, DefaultProbeHost):
        host = template.bind(lambda: document)
        if facts is not None:
            host._proxmox_facts = lambda: facts
        return host
    if template is not None:
        return template
    return DefaultProbeHost(
        secrets=secrets,
        foundations=lambda: document,
        proxmox_facts=(lambda: facts) if facts else None,
    )


def run_summary_probes(document: dict[str, Any], host: Any) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    tenant = document.get("tenant") or {}
    name = (tenant.get("name") or "").strip()
    slug = (tenant.get("slug") or "").strip()
    checks.append(
        {
            "id": "tenant",
            "label": "Tenant",
            "status": "pass" if name and slug else "fail",
            "detail": f"{name} ({slug})" if name or slug else "missing",
        }
    )
    for probe_id in SUMMARY_PROBES:
        result = run_probe(probe_id, host)
        if not isinstance(result, ProbeResult):
            result = ProbeResult("error", detail="invalid probe result")
        checks.append(
            {
                "id": probe_id,
                "label": probe_id.replace("_", " "),
                "status": result.status,
                "detail": result.detail,
            }
        )
    return checks


def summary_ok(checks: list[dict[str, str]]) -> bool:
    by_id = {item["id"]: item["status"] for item in checks}
    for required in REQUIRED_SUMMARY:
        if by_id.get(required) not in {"pass", "warn", "skip"}:
            return False
    return True


def present_status(document: dict[str, Any], secrets: Any) -> dict[str, Any]:
    presented = present_foundations(document, secrets)
    proxmox = presented.get("proxmox") or {}
    intent = presented.get("intent") or {}
    return {
        "needed": onboarding_needed(document, secrets),
        "tenant": presented.get("tenant") or {"name": "", "slug": ""},
        "proxmox": {
            "host": proxmox.get("host") or "",
            "node": proxmox.get("node") or "",
            "api_token_id": proxmox.get("api_token_id") or "",
            "api_token_set": bool(proxmox.get("api_token_set")),
        },
        "network": {
            "bridge": (presented.get("network") or {}).get("bridge") or "",
            "address": (presented.get("network") or {}).get("address") or "",
            "gateway": (presented.get("network") or {}).get("gateway") or "",
        },
        "storage": {
            "pool": (presented.get("storage") or {}).get("pool") or "",
        },
        "provider": {
            "vendor": llm_vendor(secrets),
            "api_key_set": has_llm_key(secrets),
        },
        "intent": {
            "mode": intent_mode(presented),
            "services": {
                name: {
                    "mode": (intent.get(name) or {}).get("mode"),
                    "url": (intent.get(name) or {}).get("url") or "",
                }
                for name in INTENT_KEYS
            },
        },
        "probes": presented.get("probes") or {},
    }
