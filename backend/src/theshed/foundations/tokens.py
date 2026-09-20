"""Peel Proxmox API tokens off the foundations document.

The value lives in the local secrets store. The schema keeps only
`api_token_ref`. See docs/spec/bootstrap.md.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from theshed.foundations.schema import PROXMOX_API_TOKEN_REF
from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError


def take_proxmox_api_token(document: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Return (document without the raw token, token or None)."""
    cleaned = deepcopy(document)
    proxmox = cleaned.get("proxmox")
    if not isinstance(proxmox, dict):
        return cleaned, None
    proxmox = dict(proxmox)
    raw = proxmox.pop("api_token", None)
    proxmox.pop("api_token_set", None)
    token = str(raw).strip() if raw else ""
    if token:
        proxmox["api_token_ref"] = PROXMOX_API_TOKEN_REF
    cleaned["proxmox"] = proxmox
    return cleaned, token or None


def persist_proxmox_api_token(document: dict[str, Any], secrets: Any) -> dict[str, Any]:
    cleaned, token = take_proxmox_api_token(document)
    if token and isinstance(secrets, LocalSecretsClient):
        secrets.set(PROXMOX_API_TOKEN_REF, token)
    return cleaned


def present_foundations(document: dict[str, Any], secrets: Any = None) -> dict[str, Any]:
    """GET/tool-read shape: never include the raw token."""
    presented, _token = take_proxmox_api_token(document)
    proxmox = dict(presented.get("proxmox") or {})
    ref = (proxmox.get("api_token_ref") or "").strip()
    saved = False
    if ref and secrets is not None:
        try:
            saved = bool(secrets.get(ref))
        except SecretNotFoundError:
            saved = False
    proxmox["api_token_set"] = saved
    presented["proxmox"] = proxmox
    return presented
