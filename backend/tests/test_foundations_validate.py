from theshed.foundations.schema import empty_foundations
from theshed.foundations.validate import validate_foundations


def test_empty_document_is_not_complete() -> None:
    result = validate_foundations(empty_foundations())
    assert result.ok is False
    assert "tenant.slug" in result.errors


def test_valid_minimal_foundations_pass() -> None:
    doc = empty_foundations()
    doc["tenant"] = {"name": "Riley Lab", "slug": "riley-lab"}
    doc["operator"] = {"email": "op@example.com"}
    doc["proxmox"] = {"host": "192.0.2.10", "node": "pve", "ssh_key_fingerprint": None}
    doc["network"] = {
        "bridge": "vmbr0",
        "address": "192.0.2.50/24",
        "gateway": "192.0.2.1",
        "ntp": "inherit",
    }
    doc["storage"] = {"pool": "local-lvm"}
    doc["domains"] = {"intended": []}
    result = validate_foundations(doc)
    assert result.ok is True
    assert result.errors == {}


def test_bad_slug_is_a_field_error() -> None:
    doc = empty_foundations()
    doc["tenant"] = {"name": "X", "slug": "Nope Space"}
    result = validate_foundations(doc)
    assert result.ok is False
    assert "tenant.slug" in result.errors


def test_bad_cidr_is_a_field_error() -> None:
    doc = empty_foundations()
    doc["network"] = {
        "bridge": "vmbr0",
        "address": "not-a-cidr",
        "gateway": "192.0.2.1",
        "ntp": "inherit",
    }
    result = validate_foundations(doc)
    assert "network.address" in result.errors


def test_adopt_without_url_is_a_field_error() -> None:
    doc = empty_foundations()
    doc["intent"] = {
        **empty_foundations()["intent"],
        "gitlab": {"mode": "adopt"},
    }
    result = validate_foundations(doc)
    assert "intent.gitlab.url" in result.errors


def test_unknown_keys_are_rejected() -> None:
    doc = empty_foundations()
    doc["invented"] = "nope"
    result = validate_foundations(doc)
    assert "invented" in result.errors
