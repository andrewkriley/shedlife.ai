"""Peel Proxmox API tokens off the foundations document.

The value lives in the local secrets store. The schema keeps only
`api_token_ref`. The UI collects Token ID and Token Secret; the app
combines them as `USER@REALM!tokenid=secret`. See docs/spec/bootstrap.md.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from theshed.foundations.schema import PROXMOX_API_TOKEN_REF
from theshed.secrets.client import LocalSecretsClient, SecretNotFoundError


class IncompleteProxmoxToken(ValueError):
    """One of Token ID / Token Secret was sent without the other."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Proxmox token id and secret must be saved together")
        self.errors = errors


def public_proxmox_token_id(token: str | None) -> str:
    """Return the Token ID half of `id=secret`. Empty when the value is missing."""
    raw = (token or "").strip()
    if "=" not in raw:
        return ""
    return raw.split("=", 1)[0].strip()


def assemble_proxmox_api_token(
    *,
    api_token: str | None = None,
    api_token_id: str | None = None,
    api_token_secret: str | None = None,
) -> str | None:
    """Join Token ID + Token Secret, or pass through a combined `api_token`."""
    combined = (api_token or "").strip()
    token_id = (api_token_id or "").strip()
    secret = (api_token_secret or "").strip()
    if combined:
        return combined
    if token_id and secret:
        if "=" in token_id:
            token_id = token_id.split("=", 1)[0]
        return f"{token_id}={secret}"
    if token_id or secret:
        raise IncompleteProxmoxToken(
            {
                "proxmox.api_token_id": "required with the token secret",
                "proxmox.api_token_secret": "required with the token id",
            }
        )
    return None


def take_proxmox_api_token(document: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Return (document without the raw token, token or None)."""
    cleaned = deepcopy(document)
    proxmox = cleaned.get("proxmox")
    if not isinstance(proxmox, dict):
        return cleaned, None
    proxmox = dict(proxmox)
    raw = proxmox.pop("api_token", None)
    token_id = proxmox.pop("api_token_id", None)
    token_secret = proxmox.pop("api_token_secret", None)
    proxmox.pop("api_token_set", None)
    token = assemble_proxmox_api_token(
        api_token=str(raw) if raw else None,
        api_token_id=str(token_id) if token_id else None,
        api_token_secret=str(token_secret) if token_secret else None,
    )
    if token:
        proxmox["api_token_ref"] = PROXMOX_API_TOKEN_REF
    cleaned["proxmox"] = proxmox
    return cleaned, token


def persist_proxmox_api_token(document: dict[str, Any], secrets: Any) -> dict[str, Any]:
    cleaned, token = take_proxmox_api_token(document)
    if token and isinstance(secrets, LocalSecretsClient):
        secrets.set(PROXMOX_API_TOKEN_REF, token)
    return cleaned


def present_foundations(document: dict[str, Any], secrets: Any = None) -> dict[str, Any]:
    """GET/tool-read shape: Token ID is visible; the secret never is."""
    presented, _token = take_proxmox_api_token(document)
    proxmox = dict(presented.get("proxmox") or {})
    ref = (proxmox.get("api_token_ref") or "").strip()
    saved_value = ""
    if ref and secrets is not None:
        try:
            got = secrets.get(ref)
            saved_value = got.strip() if isinstance(got, str) else ""
        except SecretNotFoundError:
            saved_value = ""
    proxmox["api_token_set"] = bool(saved_value)
    token_id = public_proxmox_token_id(saved_value)
    if token_id:
        proxmox["api_token_id"] = token_id
    else:
        proxmox.pop("api_token_id", None)
    proxmox.pop("api_token_secret", None)
    presented["proxmox"] = proxmox
    return presented
