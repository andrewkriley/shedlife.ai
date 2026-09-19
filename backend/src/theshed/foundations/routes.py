from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.foundations.store import load_foundations, record_probe_result, save_foundations
from theshed.foundations.validate import validate_foundations
from theshed.foundations.yamlutil import dump_yaml
from theshed.issues.store import record_issue
from theshed.probes.host import DefaultProbeHost
from theshed.probes.runner import SIDE_EFFECT_PROBES, run_probe

router = APIRouter(tags=["foundations"])


class FoundationsPayload(BaseModel):
    document: dict[str, Any]


@router.get("/foundations")
async def get_foundations(
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return await load_foundations(db)


@router.put("/foundations", dependencies=[Depends(require_csrf)])
async def put_foundations(
    body: FoundationsPayload,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    saved = await save_foundations(db, body.document)
    await db.commit()
    return saved


@router.post("/foundations/validate", dependencies=[Depends(require_csrf)])
async def post_validate(
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    doc = await load_foundations(db)
    result = validate_foundations(doc)
    return {"ok": result.ok, "errors": result.errors}


@router.get("/foundations/export")
async def export_foundations(
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    doc = await load_foundations(db)
    return {"yaml": dump_yaml(doc)}


@router.post("/probes/{probe_id}", dependencies=[Depends(require_csrf)])
async def post_probe(
    probe_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    if probe_id in SIDE_EFFECT_PROBES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "ssh_key_installed must run through a turn approval",
        )
    doc = await load_foundations(db)
    template = getattr(request.app.state, "probe_host", None)
    if isinstance(template, DefaultProbeHost):
        host = template.bind(lambda: doc)
    elif template is not None:
        host = template
    else:
        host = DefaultProbeHost(
            secrets=getattr(request.app.state, "secrets", None),
            foundations=lambda: doc,
        )
    result = run_probe(probe_id, host)
    if result.status == "error":
        await record_issue(
            db,
            summary=f"probe {probe_id} crashed",
            detail=result.detail,
            source="automatic",
        )
    await record_probe_result(db, probe_id, result.status, result.detail)
    await db.commit()
    return {"probe_id": probe_id, "status": result.status, "detail": result.detail}
