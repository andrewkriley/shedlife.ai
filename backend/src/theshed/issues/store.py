from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.db.models import LocalIssue
from theshed.issues.redact import classify_and_redact, redact


async def record_issue(
    db: AsyncSession,
    *,
    summary: str,
    detail: str,
    source: str,
    classification: str | None = None,
) -> LocalIssue:
    auto_class, redacted_detail = classify_and_redact(detail)
    issue = LocalIssue(
        classification=classification or auto_class,
        summary=redact(summary)[:255],
        detail=redacted_detail,
        source=source,
    )
    db.add(issue)
    await db.flush()
    return issue


async def list_issues(db: AsyncSession) -> list[LocalIssue]:
    result = await db.execute(select(LocalIssue).order_by(LocalIssue.created_at.desc()))
    return list(result.scalars().all())


async def get_issue(db: AsyncSession, issue_id: uuid.UUID) -> LocalIssue | None:
    return await db.get(LocalIssue, issue_id)
