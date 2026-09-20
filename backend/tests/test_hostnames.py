from theshed.bootstrap.hostnames import (
    SHED_HOSTNAME_LABELS,
    propose_hostnames,
)
from theshed.foundations.validate import HOSTNAME_RE, SLUG_RE


def test_labels_are_workshop_devices() -> None:
    expected = {
        "bench",
        "vise",
        "lathe",
        "solder",
        "scope",
        "meter",
        "probe",
        "wrench",
        "breadboard",
        "caliper",
    }
    assert expected <= set(SHED_HOSTNAME_LABELS)


def test_labels_are_valid_hostname_parts() -> None:
    for label in SHED_HOSTNAME_LABELS:
        assert SLUG_RE.fullmatch(label)
        assert HOSTNAME_RE.fullmatch(label)


def test_proposals_are_not_generic_servers() -> None:
    banned = {"server", "web", "app", "node", "host", "www", "shedlife"}
    assert banned.isdisjoint(SHED_HOSTNAME_LABELS)


def test_shedlife_ai_is_never_a_default() -> None:
    names = propose_hostnames()
    assert names
    assert all("shedlife.ai" not in name for name in names)
    assert propose_hostnames(base=None) == ["bench", "vise", "lathe"]


def test_skips_labels_already_in_use() -> None:
    names = propose_hostnames(used=["bench.lab.test", "Vise"])
    assert names[0] == "lathe"
    assert "bench" not in names
    assert "vise" not in names


def test_appends_operator_supplied_base() -> None:
    names = propose_hostnames(count=2, base="lab.example")
    assert names == ["bench.lab.example", "vise.lab.example"]
    assert all(HOSTNAME_RE.fullmatch(name) for name in names)


def test_invalid_base_raises() -> None:
    try:
        propose_hostnames(base="not a host")
    except ValueError as exc:
        assert "hostname" in str(exc)
    else:
        raise AssertionError("expected ValueError")
