import json

import pytest

from theshed.bootstrap.proxmox import (
    fetch_proxmox_inventory,
    iface_network,
    probe_proxmox_reachable,
    proxmox_base_url,
)
from theshed.foundations.schema import PROXMOX_API_TOKEN_REF, empty_foundations
from theshed.foundations.tokens import IncompleteProxmoxToken
from theshed.onboarding.service import (
    IncompleteAdopt,
    OnboardingError,
    apply_network,
    apply_tenant,
    discovered_defaults,
    intent_from_choice,
    onboarding_needed,
    present_status,
    save_provider,
    save_proxmox_token,
    summary_ok,
)
from theshed.secrets.client import LocalSecretsClient


def test_proxmox_base_url_adds_the_api_port() -> None:
    assert proxmox_base_url("192.0.2.10") == "https://192.0.2.10:8006"
    assert proxmox_base_url("https://pve.example:8006/") == "https://pve.example:8006"


def test_reachable_treats_401_as_up() -> None:
    ok, detail = probe_proxmox_reachable(
        "192.0.2.10", http_get=lambda _url, _timeout, _headers=None: (401, "")
    )
    assert ok is True
    assert "401" in detail


def test_reachable_reports_transport_failure() -> None:
    def boom(_url: str, _timeout: float, _headers=None) -> tuple[int, str]:
        raise RuntimeError("connection refused")

    ok, detail = probe_proxmox_reachable("192.0.2.10", http_get=boom)
    assert ok is False
    assert "connection refused" in detail


def test_inventory_lists_nodes_bridges_and_pools() -> None:
    def http_get(url: str, _timeout: float, _headers=None) -> tuple[int, str]:
        if url.endswith("/version"):
            return 200, json.dumps({"data": {"version": "8.3"}})
        if url.endswith("/nodes"):
            return 200, json.dumps(
                {
                    "data": [
                        {
                            "node": "pve",
                            "maxcpu": 8,
                            "maxmem": 32 * 1024**3,
                            "maxdisk": 200 * 1024**3,
                        }
                    ]
                }
            )
        if url.endswith("/network"):
            return 200, json.dumps(
                {
                    "data": [
                        {
                            "iface": "vmbr0",
                            "type": "bridge",
                            "address": "192.0.2.10",
                            "netmask": "255.255.255.0",
                            "gateway": "192.0.2.1",
                        },
                        {"iface": "eth0", "type": "eth"},
                    ]
                }
            )
        if url.endswith("/storage"):
            return 200, json.dumps({"data": [{"storage": "local-lvm"}, {"storage": "local"}]})
        return 404, ""

    facts = fetch_proxmox_inventory("192.0.2.10", "root@pam!shed=secret", http_get=http_get)
    assert facts["version"] == "8.3"
    assert facts["nodes"] == ["pve"]
    assert facts["bridges"] == ["vmbr0"]
    assert facts["pools"] == ["local-lvm", "local"]
    assert facts["vcpu"] == 8
    assert facts["ram_gb"] == 32
    assert facts["disk_gb"] == 200
    assert facts["address"] == "192.0.2.10/24"
    assert facts["gateway"] == "192.0.2.1"
    assert facts["networks"]["vmbr0"] == {"address": "192.0.2.10/24", "gateway": "192.0.2.1"}


def test_iface_network_reads_cidr_or_netmask() -> None:
    assert iface_network({"cidr": "10.0.0.2/24", "gateway": "10.0.0.1"}) == {
        "address": "10.0.0.2/24",
        "gateway": "10.0.0.1",
    }
    assert iface_network({"address": "10.0.0.2", "cidr": "24", "gateway": "10.0.0.1"}) == {
        "address": "10.0.0.2/24",
        "gateway": "10.0.0.1",
    }
    assert iface_network({"address": "10.0.0.2", "netmask": "255.255.255.0"}) == {
        "address": "10.0.0.2/24",
        "gateway": "",
    }


def test_inventory_rejects_a_bad_token() -> None:
    with pytest.raises(PermissionError, match="rejected"):
        fetch_proxmox_inventory(
            "192.0.2.10",
            "bad",
            http_get=lambda _url, _timeout, _headers=None: (401, ""),
        )


def test_onboarding_needed_until_minimum_facts_exist() -> None:
    secrets = LocalSecretsClient()
    doc = empty_foundations()
    assert onboarding_needed(doc, secrets) is True
    secrets.set("local://providers/llm/api_key", "sk-ant-api03-testkey")
    secrets.set("local://providers/llm/vendor", "anthropic")
    secrets.set(PROXMOX_API_TOKEN_REF, "root@pam!shed=secret")
    doc["tenant"] = {"name": "Riley Lab", "slug": "riley-lab"}
    doc["proxmox"]["host"] = "192.0.2.10"
    doc["proxmox"]["api_token_ref"] = PROXMOX_API_TOKEN_REF
    assert onboarding_needed(doc, secrets) is False


def test_present_status_shows_token_id_not_the_secret() -> None:
    secrets = LocalSecretsClient()
    secrets.set(PROXMOX_API_TOKEN_REF, "root@pam!shed=secret-token")
    doc = empty_foundations()
    doc["proxmox"]["host"] = "192.0.2.10"
    doc["proxmox"]["api_token_ref"] = PROXMOX_API_TOKEN_REF
    status = present_status(doc, secrets)
    assert status["proxmox"]["api_token_id"] == "root@pam!shed"
    assert status["proxmox"]["api_token_set"] is True
    assert "secret-token" not in str(status)


def test_intent_build_writes_all_build() -> None:
    intent = intent_from_choice("build", {})
    assert intent["gitlab"]["mode"] == "build"
    assert intent["dns"]["mode"] == "greenfield"


def test_intent_adopt_requires_a_url() -> None:
    with pytest.raises(IncompleteAdopt):
        intent_from_choice("adopt", {})


def test_intent_adopt_keeps_unspecified_services_on_build() -> None:
    intent = intent_from_choice("adopt", {"gitlab": "https://git.example.test"})
    assert intent["gitlab"] == {"mode": "adopt", "url": "https://git.example.test"}
    assert intent["infisical"]["mode"] == "build"
    assert intent["dns"]["mode"] == "greenfield"


def test_discovered_defaults_fill_empty_keys_only() -> None:
    doc = empty_foundations()
    doc["proxmox"]["node"] = "already"
    facts = {
        "nodes": ["pve"],
        "bridges": ["vmbr0"],
        "pools": ["local-lvm"],
        "address": "192.0.2.10/24",
        "gateway": "192.0.2.1",
    }
    patch = discovered_defaults(doc, facts)
    assert "proxmox" not in patch
    assert patch["network"]["bridge"] == "vmbr0"
    assert patch["network"]["address"] == "192.0.2.10/24"
    assert patch["network"]["gateway"] == "192.0.2.1"
    assert patch["storage"]["pool"] == "local-lvm"


def test_discovered_defaults_read_cidr_from_the_chosen_bridge() -> None:
    facts = {
        "nodes": ["pve"],
        "bridges": ["vmbr1"],
        "pools": ["tank"],
        "networks": {
            "vmbr1": {"address": "10.0.0.2/24", "gateway": "10.0.0.1"},
        },
    }
    patch = discovered_defaults(empty_foundations(), facts)
    assert patch["network"]["bridge"] == "vmbr1"
    assert patch["network"]["address"] == "10.0.0.2/24"
    assert patch["network"]["gateway"] == "10.0.0.1"
    assert patch["storage"]["pool"] == "tank"


def test_apply_network_saves_discovered_choices() -> None:
    doc = apply_network(
        empty_foundations(),
        bridge="vmbr0",
        address="192.0.2.10/24",
        gateway="192.0.2.1",
        pool="local-lvm",
    )
    assert doc["network"]["bridge"] == "vmbr0"
    assert doc["network"]["address"] == "192.0.2.10/24"
    assert doc["network"]["gateway"] == "192.0.2.1"
    assert doc["storage"]["pool"] == "local-lvm"


def test_apply_network_rejects_a_bad_cidr() -> None:
    with pytest.raises(OnboardingError) as caught:
        apply_network(empty_foundations(), address="not-a-cidr")
    assert "network.address" in caught.value.errors


def test_apply_network_rejects_a_bad_gateway() -> None:
    with pytest.raises(OnboardingError) as caught:
        apply_network(empty_foundations(), gateway="not-an-ip")
    assert "network.gateway" in caught.value.errors


def test_apply_tenant_rejects_a_bad_slug() -> None:
    with pytest.raises(OnboardingError) as caught:
        apply_tenant(empty_foundations(), "Lab", "Riley Lab")
    assert "tenant.slug" in caught.value.errors


def test_save_token_joins_id_and_secret() -> None:
    secrets = LocalSecretsClient()
    doc = save_proxmox_token(
        empty_foundations(),
        secrets,
        api_token_id="root@pam!shed",
        api_token_secret="secret-token",
    )
    assert secrets.get(PROXMOX_API_TOKEN_REF) == "root@pam!shed=secret-token"
    assert "api_token_secret" not in doc["proxmox"]


def test_save_token_keeps_an_existing_secret_on_rerun() -> None:
    secrets = LocalSecretsClient()
    doc = empty_foundations()
    doc["proxmox"]["api_token_ref"] = PROXMOX_API_TOKEN_REF
    secrets.set(PROXMOX_API_TOKEN_REF, "root@pam!shed=secret-token")
    saved = save_proxmox_token(doc, secrets)
    assert secrets.get(PROXMOX_API_TOKEN_REF) == "root@pam!shed=secret-token"
    assert saved["proxmox"]["api_token_ref"] == PROXMOX_API_TOKEN_REF


def test_save_token_attaches_a_ref_when_the_secret_already_exists() -> None:
    secrets = LocalSecretsClient()
    secrets.set(PROXMOX_API_TOKEN_REF, "root@pam!shed=secret-token")
    saved = save_proxmox_token(empty_foundations(), secrets)
    assert saved["proxmox"]["api_token_ref"] == PROXMOX_API_TOKEN_REF


def test_save_token_rejects_an_id_without_the_secret() -> None:
    with pytest.raises(IncompleteProxmoxToken):
        save_proxmox_token(empty_foundations(), LocalSecretsClient(), api_token_id="root@pam!shed")


def test_save_provider_rejects_a_subscription() -> None:
    with pytest.raises(Exception, match="subscription"):
        save_provider(LocalSecretsClient(), "anthropic", "claude subscription")


def test_save_provider_rerun_keeps_the_saved_key() -> None:
    secrets = LocalSecretsClient()
    save_provider(secrets, "anthropic", "sk-ant-api03-testkey")
    vendor = save_provider(secrets, "anthropic", "")
    assert vendor == "anthropic"
    assert secrets.get("local://providers/llm/api_key") == "sk-ant-api03-testkey"


def test_summary_ok_requires_the_minimum_passes() -> None:
    assert (
        summary_ok(
            [
                {"id": "tenant", "status": "pass"},
                {"id": "provider", "status": "pass"},
                {"id": "llm_key", "status": "pass"},
                {"id": "proxmox_api", "status": "pass"},
                {"id": "outbound_https", "status": "fail"},
            ]
        )
        is True
    )
    assert (
        summary_ok(
            [
                {"id": "tenant", "status": "pass"},
                {"id": "provider", "status": "pass"},
                {"id": "llm_key", "status": "fail"},
                {"id": "proxmox_api", "status": "pass"},
            ]
        )
        is False
    )
