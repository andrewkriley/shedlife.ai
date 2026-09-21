import pytest

from theshed.foundations.schema import PROXMOX_API_TOKEN_REF, empty_foundations
from theshed.foundations.tokens import (
    IncompleteProxmoxToken,
    persist_proxmox_api_token,
    present_foundations,
    public_proxmox_token_id,
    take_proxmox_api_token,
)
from theshed.secrets.client import LocalSecretsClient


def test_take_proxmox_api_token_strips_the_raw_value() -> None:
    doc = empty_foundations()
    doc["proxmox"]["api_token"] = "root@pam!shed=secret-token"
    cleaned, token = take_proxmox_api_token(doc)
    assert token == "root@pam!shed=secret-token"
    assert "api_token" not in cleaned["proxmox"]
    assert cleaned["proxmox"]["api_token_ref"] == PROXMOX_API_TOKEN_REF


def test_take_combines_token_id_and_secret() -> None:
    doc = empty_foundations()
    doc["proxmox"]["api_token_id"] = "root@pam!shed"
    doc["proxmox"]["api_token_secret"] = "secret-token"
    cleaned, token = take_proxmox_api_token(doc)
    assert token == "root@pam!shed=secret-token"
    assert "api_token_id" not in cleaned["proxmox"]
    assert "api_token_secret" not in cleaned["proxmox"]
    assert cleaned["proxmox"]["api_token_ref"] == PROXMOX_API_TOKEN_REF


def test_take_rejects_a_token_id_without_the_secret() -> None:
    doc = empty_foundations()
    doc["proxmox"]["api_token_id"] = "root@pam!shed"
    with pytest.raises(IncompleteProxmoxToken) as caught:
        take_proxmox_api_token(doc)
    assert "proxmox.api_token_secret" in caught.value.errors


def test_public_token_id_never_returns_the_secret() -> None:
    assert public_proxmox_token_id("root@pam!shed=secret-token") == "root@pam!shed"
    assert public_proxmox_token_id("just-a-secret") == ""
    assert public_proxmox_token_id("") == ""


def test_persist_and_present_never_echo_the_token() -> None:
    secrets = LocalSecretsClient()
    doc = empty_foundations()
    doc["proxmox"]["host"] = "192.0.2.10"
    doc["proxmox"]["api_token"] = "root@pam!shed=secret-token"

    stored = persist_proxmox_api_token(doc, secrets)
    assert "api_token" not in stored["proxmox"]
    assert secrets.get(PROXMOX_API_TOKEN_REF) == "root@pam!shed=secret-token"

    presented = present_foundations(stored, secrets)
    assert presented["proxmox"]["api_token_set"] is True
    assert presented["proxmox"]["api_token_id"] == "root@pam!shed"
    assert "api_token" not in presented["proxmox"]
    assert "api_token_secret" not in presented["proxmox"]
    assert "secret-token" not in str(presented)
