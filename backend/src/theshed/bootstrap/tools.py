"""Tool executor for bootstrap.intake."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from theshed.agents.tool_loop import ToolCall
from theshed.foundations.store import load_foundations, patch_foundations, record_probe_result
from theshed.foundations.validate import validate_foundations
from theshed.foundations.yamlutil import dump_yaml
from theshed.issues.store import record_issue
from theshed.probes.host import DefaultProbeHost
from theshed.probes.runner import ProbeResult, run_probe

ToolExecutor = Callable[[ToolCall], Awaitable[str]]


def _bind_host(probe_host: Any, doc: dict[str, Any]) -> Any:
    if isinstance(probe_host, DefaultProbeHost):
        return probe_host.bind(lambda: doc)
    return probe_host


async def _persist_probe(db: Any, probe_id: str, result: ProbeResult) -> None:
    if result.status == "error":
        await record_issue(
            db,
            summary=f"probe {probe_id} crashed",
            detail=result.detail,
            source="automatic",
        )
    await record_probe_result(db, probe_id, result.status, result.detail)
    await db.commit()


def make_bootstrap_tool_executor(db: Any, probe_host: Any) -> ToolExecutor:
    async def execute(call: ToolCall) -> str:
        name = call.tool_name
        args = call.arguments or {}
        if name == "foundations_write":
            doc = await patch_foundations(db, args.get("patch") or {})
            await db.commit()
            return json.dumps(doc)
        if name == "foundations_read":
            return json.dumps(await load_foundations(db))
        if name == "foundations_validate":
            result = validate_foundations(await load_foundations(db))
            return json.dumps({"ok": result.ok, "errors": result.errors})
        if name == "run_probe":
            probe_id = str(args.get("probe_id") or "")
            doc = await load_foundations(db)
            result = run_probe(probe_id, _bind_host(probe_host, doc))
            await _persist_probe(db, probe_id, result)
            return json.dumps(
                {"probe_id": probe_id, "status": result.status, "detail": result.detail}
            )
        if name == "export_state":
            return dump_yaml(await load_foundations(db))
        if name == "install_ssh_key":
            doc = await load_foundations(db)
            result = run_probe("ssh_key_installed", _bind_host(probe_host, doc))
            await _persist_probe(db, "ssh_key_installed", result)
            return json.dumps({"status": result.status, "detail": result.detail})
        raise NotImplementedError(name)

    return execute
