from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime

from theshed.db.models import FoundationDocument
from theshed.foundations.schema import empty_foundations, merge_foundations


def _stamp() -> datetime:
    return datetime.now(UTC)


async def load_foundations(db: AsyncSession) -> dict[str, Any]:
    row = await db.get(FoundationDocument, 1)
    if row is None:
        return empty_foundations()
    return dict(row.document)


async def save_foundations(db: AsyncSession, document: dict[str, Any]) -> dict[str, Any]:
    row = await db.get(FoundationDocument, 1)
    if row is None:
        row = FoundationDocument(id=1, document=document, updated_at=_stamp())
        db.add(row)
    else:
        row.document = document
        row.updated_at = _stamp()
    await db.flush()
    return document


async def patch_foundations(db: AsyncSession, patch: dict[str, Any]) -> dict[str, Any]:
    current = await load_foundations(db)
    merged = merge_foundations(current, patch)
    return await save_foundations(db, merged)


async def record_probe_result(db: AsyncSession, probe_id: str, status: str, detail: str) -> dict[str, Any]:
    doc = await load_foundations(db)
    probes = dict(doc.get("probes") or {})
    probes[probe_id] = {
        "status": status,
        "at": datetime.now(UTC).isoformat(),
        "detail": detail,
    }
    return await patch_foundations(db, {"probes": probes})
