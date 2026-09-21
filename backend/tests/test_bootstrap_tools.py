import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.tool_loop import ToolCall
from theshed.bootstrap.tools import make_bootstrap_tool_executor
from theshed.foundations.schema import PROXMOX_API_TOKEN_REF, empty_foundations
from theshed.foundations.store import load_foundations, save_foundations
from theshed.probes.host import DefaultProbeHost
from theshed.secrets.client import LocalSecretsClient


@pytest.mark.asyncio
async def test_foundations_write_and_validate_round_trip(db_session: AsyncSession) -> None:
    execute = make_bootstrap_tool_executor(db_session, DefaultProbeHost())
    written = await execute(
        ToolCall(
            tool_name="foundations_write",
            arguments={"patch": {"tenant": {"name": "Lab", "slug": "lab"}}},
            has_side_effects=False,
        )
    )
    doc = json.loads(written)
    assert doc["tenant"]["slug"] == "lab"

    validated = json.loads(
        await execute(ToolCall(tool_name="foundations_validate", arguments={}, has_side_effects=False))
    )
    assert validated["ok"] is False
    assert "operator.email" in validated["errors"]


@pytest.mark.asyncio
async def test_foundations_write_stores_a_proxmox_api_token(
    db_session: AsyncSession,
) -> None:
    secrets = LocalSecretsClient()
    execute = make_bootstrap_tool_executor(db_session, DefaultProbeHost(secrets=secrets))
    written = json.loads(
        await execute(
            ToolCall(
                tool_name="foundations_write",
                arguments={
                    "patch": {
                        "proxmox": {
                            "host": "192.0.2.10",
                            "api_token_id": "root@pam!shed",
                            "api_token_secret": "secret-token",
                        }
                    }
                },
                has_side_effects=False,
            )
        )
    )
    assert written["proxmox"]["api_token_set"] is True
    assert "api_token" not in written["proxmox"]
    assert secrets.get(PROXMOX_API_TOKEN_REF) == "root@pam!shed=secret-token"


@pytest.mark.asyncio
async def test_run_probe_persists_result(db_session: AsyncSession) -> None:
    secrets = LocalSecretsClient()
    secrets.set("local://providers/llm/api_key", "sk-ant-api03-test")
    host = DefaultProbeHost(secrets=secrets)
    execute = make_bootstrap_tool_executor(db_session, host)
    await save_foundations(db_session, empty_foundations())
    await db_session.commit()

    raw = await execute(
        ToolCall(
            tool_name="run_probe",
            arguments={"probe_id": "llm_key"},
            has_side_effects=False,
        )
    )
    payload = json.loads(raw)
    assert payload["status"] == "pass"
    stored = await load_foundations(db_session)
    assert stored["probes"]["llm_key"]["status"] == "pass"


@pytest.mark.asyncio
async def test_unknown_tool_is_refused(db_session: AsyncSession) -> None:
    execute = make_bootstrap_tool_executor(db_session, DefaultProbeHost())
    with pytest.raises(NotImplementedError):
        await execute(ToolCall(tool_name="invent_topology", arguments={}, has_side_effects=False))


def test_default_host_uses_injected_http() -> None:
    calls: list[str] = []

    def http_get(url: str, _timeout: float) -> tuple[int, str]:
        calls.append(url)
        return 200, ""

    host = DefaultProbeHost(http_get=http_get)
    assert host.outbound_https().status == "pass"
    assert calls == ["https://example.com"]


def test_default_host_bind_sees_foundations() -> None:
    secrets = LocalSecretsClient()
    secrets.set(PROXMOX_API_TOKEN_REF, "root@pam!shed=secret-token")
    host = DefaultProbeHost(
        secrets=secrets,
        http_get=lambda url, _t: (200, "") if "8006" in url else (500, ""),
        foundations=dict,
    )
    bound = host.bind(
        lambda: {
            "proxmox": {
                "host": "192.0.2.10",
                "api_token_ref": PROXMOX_API_TOKEN_REF,
            }
        }
    )
    assert bound.proxmox_api().status == "pass"


def test_proxmox_api_fails_without_a_token() -> None:
    host = DefaultProbeHost(
        http_get=lambda url, _t: (200, ""),
        foundations=lambda: {"proxmox": {"host": "192.0.2.10"}},
    )
    assert host.proxmox_api().status == "fail"
    assert "token" in (host.proxmox_api().detail or "")


@pytest.mark.asyncio
async def test_discovery_lists_do_not_write_foundations(db_session: AsyncSession) -> None:
    host = DefaultProbeHost(
        proxmox_facts=lambda: {
            "nodes": ["pve"],
            "bridges": ["vmbr0"],
            "pools": ["local-lvm"],
            "version": "8.3.5",
        }
    )
    execute = make_bootstrap_tool_executor(db_session, host)
    await save_foundations(db_session, empty_foundations())
    await db_session.commit()

    raw = await execute(
        ToolCall(tool_name="list_bridges", arguments={}, has_side_effects=False)
    )
    payload = json.loads(raw)
    assert payload["status"] == "found"
    assert payload["provenance"] == "discovered"
    assert payload["values"] == {"bridges": ["vmbr0"]}

    stored = await load_foundations(db_session)
    assert stored["network"]["bridge"] == ""
    assert "list_bridges" not in (stored.get("probes") or {})


@pytest.mark.asyncio
async def test_discover_gitlab_reads_intent_and_skips_bodies(db_session: AsyncSession) -> None:
    def http_get(url: str, _timeout: float) -> tuple[int, str]:
        return 200, "token=should-not-leak"

    host = DefaultProbeHost(http_get=http_get)
    execute = make_bootstrap_tool_executor(db_session, host)
    doc = empty_foundations()
    doc["intent"]["gitlab"] = {"mode": "adopt", "url": "https://git.example.test"}
    await save_foundations(db_session, doc)
    await db_session.commit()

    raw = await execute(
        ToolCall(tool_name="discover_gitlab", arguments={}, has_side_effects=False)
    )
    payload = json.loads(raw)
    assert payload["status"] == "found"
    assert payload["values"]["reachable"] is True
    assert "should-not-leak" not in raw

    stored = await load_foundations(db_session)
    assert stored["intent"]["gitlab"]["url"] == "https://git.example.test"
    assert "discover_gitlab" not in (stored.get("probes") or {})


@pytest.mark.asyncio
async def test_propose_hostnames_skips_used_and_does_not_write(
    db_session: AsyncSession,
) -> None:
    execute = make_bootstrap_tool_executor(db_session, DefaultProbeHost())
    doc = empty_foundations()
    doc["domains"] = {"intended": ["bench.lab.test"]}
    await save_foundations(db_session, doc)
    await db_session.commit()

    raw = await execute(
        ToolCall(
            tool_name="propose_hostnames",
            arguments={"count": 2, "base": "lab.test"},
            has_side_effects=False,
        )
    )
    payload = json.loads(raw)
    assert payload["status"] == "found"
    assert payload["provenance"] == "proposed"
    assert payload["values"]["hostnames"] == ["vise.lab.test", "lathe.lab.test"]
    assert all("shedlife.ai" not in name for name in payload["values"]["hostnames"])

    stored = await load_foundations(db_session)
    assert stored["domains"]["intended"] == ["bench.lab.test"]
