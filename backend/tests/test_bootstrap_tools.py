import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.tool_loop import ToolCall
from theshed.bootstrap.tools import make_bootstrap_tool_executor
from theshed.foundations.schema import empty_foundations
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
    host = DefaultProbeHost(
        http_get=lambda url, _t: (200, "") if "8006" in url else (500, ""),
        foundations=lambda: {},
    )
    bound = host.bind(lambda: {"proxmox": {"host": "192.0.2.10"}})
    assert bound.proxmox_api().status == "pass"
