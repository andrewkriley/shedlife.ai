from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from theshed.debug import log as debug_log

router = APIRouter(prefix="/debug", tags=["debug"])


class EnabledBody(BaseModel):
    enabled: bool


class ClientEventBody(BaseModel):
    source: str = "ui"
    event: str
    message: str
    level: str = "info"
    detail: dict[str, Any] | None = None


@router.get("/status")
async def debug_status() -> dict[str, bool]:
    return {"enabled": debug_log.is_enabled()}


@router.post("/enabled")
async def set_debug_enabled(body: EnabledBody) -> dict[str, bool]:
    debug_log.set_enabled(body.enabled)
    debug_log.record("debug", "toggle", f"Debug {'on' if body.enabled else 'off'}")
    return {"enabled": debug_log.is_enabled()}


@router.get("/logs")
async def debug_logs() -> dict[str, Any]:
    return {"enabled": debug_log.is_enabled(), "events": debug_log.snapshot()}


@router.post("/events")
async def post_debug_event(body: ClientEventBody) -> dict[str, str]:
    debug_log.record(
        body.source,
        body.event,
        body.message,
        level=body.level,
        detail=body.detail,
    )
    return {"status": "ok"}
