from theshed.foundations.schema import PROXMOX_API_TOKEN_REF, empty_foundations
from theshed.foundations.tokens import (
    persist_proxmox_api_token,
    present_foundations,
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
    assert "api_token" not in presented["proxmox"]
    assert "secret-token" not in str(presented)
