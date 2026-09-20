"""Deterministic foundations checks, per docs/prd/bootstrap.md playbook 2."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any

from theshed.foundations.schema import INTENT_KEYS, KNOWN_TOP_LEVEL

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)


@dataclass
class ValidationResult:
    ok: bool
    errors: dict[str, str] = field(default_factory=dict)


def validate_foundations(doc: dict[str, Any]) -> ValidationResult:
    errors: dict[str, str] = {}
    for key in doc:
        if key not in KNOWN_TOP_LEVEL:
            errors[key] = "unknown field"

    tenant = doc.get("tenant") or {}
    if not (tenant.get("name") or "").strip():
        errors.setdefault("tenant.name", "required")
    slug = (tenant.get("slug") or "").strip()
    if not slug:
        errors.setdefault("tenant.slug", "required")
    elif not SLUG_RE.fullmatch(slug):
        errors["tenant.slug"] = "must match [a-z0-9-]+"

    email = ((doc.get("operator") or {}).get("email") or "").strip()
    if not email:
        errors.setdefault("operator.email", "required")
    elif not EMAIL_RE.fullmatch(email):
        errors["operator.email"] = "invalid email"

    proxmox = doc.get("proxmox") or {}
    if not (proxmox.get("host") or "").strip():
        errors.setdefault("proxmox.host", "required")
    if not (proxmox.get("api_token_ref") or "").strip():
        errors.setdefault("proxmox.api_token", "required")

    network = doc.get("network") or {}
    address = (network.get("address") or "").strip()
    if address:
        try:
            ipaddress.ip_network(address, strict=False)
        except ValueError:
            errors["network.address"] = "must be CIDR (address/prefix)"
    gateway = (network.get("gateway") or "").strip()
    if gateway:
        try:
            ipaddress.ip_address(gateway)
        except ValueError:
            errors["network.gateway"] = "must be an IP address"

    intent = doc.get("intent") or {}
    for name in INTENT_KEYS:
        entry = intent.get(name) or {}
        mode = entry.get("mode")
        if name == "dns":
            if mode not in {"greenfield", "brownfield"}:
                errors[f"intent.{name}.mode"] = "must be greenfield or brownfield"
            elif mode == "brownfield" and not (entry.get("url") or "").strip():
                errors[f"intent.{name}.url"] = "required when adopting"
        else:
            if mode not in {"build", "adopt"}:
                errors[f"intent.{name}.mode"] = "must be build or adopt"
            elif mode == "adopt" and not (entry.get("url") or "").strip():
                errors[f"intent.{name}.url"] = "required when adopting"

    for hostname in (doc.get("domains") or {}).get("intended") or []:
        if hostname and not HOSTNAME_RE.fullmatch(str(hostname)):
            errors.setdefault("domains.intended", f"invalid hostname: {hostname}")

    return ValidationResult(ok=not errors, errors=errors)
