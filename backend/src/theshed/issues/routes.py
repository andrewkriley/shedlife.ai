from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.session import get_session
from theshed.issues.store import get_issue, list_issues, record_issue

router = APIRouter(prefix="/issues", tags=["issues"])


class FileIssueRequest(BaseModel):
    summary: str
    detail: str
    classification: str | None = None


def _to_dict(issue: Any) -> dict[str, Any]:
    return {
        "id": str(issue.id),
        "classification": issue.classification,
        "summary": issue.summary,
        "detail": issue.detail,
        "source": issue.source,
        "filed_externally": issue.filed_externally,
        "created_at": issue.created_at.isoformat(),
    }


@router.get("")
async def get_issues(
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> list[dict[str, Any]]:
    return [_to_dict(issue) for issue in await list_issues(db)]


@router.post("", dependencies=[Depends(require_csrf)])
async def post_issue(
    body: FileIssueRequest,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    issue = await record_issue(
        db,
        summary=body.summary,
        detail=body.detail,
        source="operator",
        classification=body.classification,
    )
    await db.commit()
    return _to_dict(issue)


@router.post("/{issue_id}/file-upstream", dependencies=[Depends(require_csrf)])
async def file_upstream(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    issue = await get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    if issue.classification != "product-bug":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only product-bug issues can be filed upstream")
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        "Upstream filing is opt-in and needs a GitHub token in local secrets",
    )
