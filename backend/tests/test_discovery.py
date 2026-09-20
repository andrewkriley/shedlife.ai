from theshed.bootstrap.discovery import (
    DISCOVERY_TOOLS,
    DiscoveryHost,
    DiscoveryResult,
    run_discovery,
)
from theshed.foundations.schema import empty_foundations


def _facts(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "nodes": ["pve"],
        "bridges": ["vmbr0", "vmbr1"],
        "pools": ["local-lvm", "local"],
        "version": "8.3.5",
    }
    base.update(overrides)
    return base


def _doc_with_intent(name: str, **entry: object) -> dict[str, object]:
    doc = empty_foundations()
    intent = dict(doc["intent"])
    current = dict(intent[name])
    current.update(entry)
    intent[name] = current
    doc["intent"] = intent
    return doc


def test_discovery_tool_names_are_the_agreed_set() -> None:
    assert DISCOVERY_TOOLS == (
        "list_proxmox_nodes",
        "list_bridges",
        "list_storage_pools",
        "proxmox_version",
        "discover_gitlab",
        "discover_infisical",
        "discover_dns",
        "discover_k3s",
    )


def test_list_proxmox_nodes_returns_injected_facts() -> None:
    host = DiscoveryHost(proxmox_facts=lambda: _facts())
    result = run_discovery("list_proxmox_nodes", host)
    assert result.status == "found"
    assert result.provenance == "discovered"
    assert result.values == {"nodes": ["pve"]}


def test_list_bridges_and_pools_return_injected_facts() -> None:
    host = DiscoveryHost(proxmox_facts=lambda: _facts())
    bridges = run_discovery("list_bridges", host)
    pools = run_discovery("list_storage_pools", host)
    assert bridges.status == "found"
    assert bridges.values == {"bridges": ["vmbr0", "vmbr1"]}
    assert pools.status == "found"
    assert pools.values == {"pools": ["local-lvm", "local"]}


def test_proxmox_version_returns_injected_version() -> None:
    host = DiscoveryHost(proxmox_facts=lambda: _facts())
    result = run_discovery("proxmox_version", host)
    assert result.status == "found"
    assert result.values == {"version": "8.3.5"}


def test_host_inventory_skips_when_facts_are_unavailable() -> None:
    host = DiscoveryHost()
    for name in (
        "list_proxmox_nodes",
        "list_bridges",
        "list_storage_pools",
        "proxmox_version",
    ):
        result = run_discovery(name, host)
        assert result.status == "skip"
        assert "unavailable" in result.detail


def test_proxmox_version_fails_when_facts_omit_it() -> None:
    host = DiscoveryHost(proxmox_facts=lambda: _facts(version=""))
    result = run_discovery("proxmox_version", host)
    assert result.status == "fail"
    assert result.values == {}


def test_empty_host_lists_are_still_found() -> None:
    host = DiscoveryHost(proxmox_facts=lambda: {"nodes": [], "bridges": [], "pools": []})
    assert run_discovery("list_proxmox_nodes", host).values == {"nodes": []}
    assert run_discovery("list_bridges", host).values == {"bridges": []}
    assert run_discovery("list_storage_pools", host).values == {"pools": []}


def test_discover_gitlab_skips_when_intent_is_build() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent("gitlab", mode="build"),
        http_get=lambda _url, _t: (200, "should-not-run"),
    )
    result = run_discovery("discover_gitlab", host)
    assert result.status == "skip"
    assert "build" in result.detail


def test_discover_gitlab_found_does_not_echo_http_body() -> None:
    calls: list[str] = []

    def http_get(url: str, _timeout: float) -> tuple[int, str]:
        calls.append(url)
        return 200, "PRIVATE TOKEN=sk-secret"

    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent(
            "gitlab", mode="adopt", url="https://git.example.test"
        ),
        http_get=http_get,
    )
    result = run_discovery("discover_gitlab", host)
    assert result.status == "found"
    assert result.provenance == "discovered"
    assert result.values == {
        "url": "https://git.example.test",
        "http_status": 200,
        "reachable": True,
    }
    assert calls == ["https://git.example.test"]
    dumped = result.as_dict()
    assert "sk-secret" not in str(dumped)
    assert "PRIVATE" not in str(dumped)


def test_discover_gitlab_fails_on_server_error() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent(
            "gitlab", mode="adopt", url="https://git.example.test"
        ),
        http_get=lambda _url, _t: (503, "<html>down</html>"),
    )
    result = run_discovery("discover_gitlab", host)
    assert result.status == "fail"
    assert result.values == {"http_status": 503}
    assert "html" not in result.detail


def test_discover_gitlab_fails_on_transport_error() -> None:
    def http_get(_url: str, _timeout: float) -> tuple[int, str]:
        raise RuntimeError("connection refused")

    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent(
            "gitlab", mode="adopt", url="https://git.example.test"
        ),
        http_get=http_get,
    )
    result = run_discovery("discover_gitlab", host)
    assert result.status == "fail"
    assert "connection refused" in result.detail


def test_discover_infisical_skips_unless_adopt() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent("infisical", mode="build"),
        http_get=lambda _url, _t: (200, ""),
    )
    assert run_discovery("discover_infisical", host).status == "skip"


def test_discover_dns_skips_unless_brownfield() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent("dns", mode="greenfield"),
        http_get=lambda _url, _t: (200, ""),
    )
    assert run_discovery("discover_dns", host).status == "skip"


def test_discover_dns_found_when_brownfield_url_answers() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent(
            "dns", mode="brownfield", url="https://pdns.example.test"
        ),
        http_get=lambda _url, _t: (401, "need api key"),
    )
    result = run_discovery("discover_dns", host)
    assert result.status == "found"
    assert result.values["http_status"] == 401
    assert "need api key" not in str(result.as_dict())


def test_discover_k3s_skips_when_only_kubeconfig_ref() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent(
            "k3s", mode="adopt", kubeconfig_ref="local://intent/k3s/kubeconfig"
        ),
        http_get=lambda _url, _t: (200, "should-not-run"),
    )
    result = run_discovery("discover_k3s", host)
    assert result.status == "skip"
    assert "kubeconfig_ref" in result.detail


def test_discover_k3s_found_when_url_is_reachable() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent(
            "k3s", mode="adopt", url="https://k3s.example.test:6443"
        ),
        http_get=lambda _url, _t: (200, ""),
    )
    result = run_discovery("discover_k3s", host)
    assert result.status == "found"
    assert result.values["reachable"] is True


def test_discover_k3s_fails_when_adopt_has_neither_url_nor_kubeconfig() -> None:
    host = DiscoveryHost(
        foundations=lambda: _doc_with_intent("k3s", mode="adopt"),
        http_get=lambda _url, _t: (200, ""),
    )
    result = run_discovery("discover_k3s", host)
    assert result.status == "fail"
    assert "url" in result.detail


def test_unknown_discovery_tool_is_an_error() -> None:
    result = run_discovery("invent_topology", DiscoveryHost())
    assert result.status == "error"
    assert "unknown" in result.detail


def test_host_exception_is_error() -> None:
    class Boom(DiscoveryHost):
        def list_bridges(self) -> DiscoveryResult:
            raise RuntimeError("facts socket closed")

    result = run_discovery("list_bridges", Boom())
    assert result.status == "error"
    assert "facts socket closed" in result.detail
