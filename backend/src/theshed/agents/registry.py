"""Sub-agent registry lookups, per docs/spec/core-agentic-loop.md. Thin on
purpose — the registry itself is just the `sub_agents` table; this module
exists so callers don't hand-write the same queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.db.models import SubAgent


async def list_sub_agents(db: AsyncSession) -> list[SubAgent]:
    result = await db.execute(select(SubAgent))
    return list(result.scalars().all())


async def get_sub_agent(db: AsyncSession, sub_agent_id: str) -> SubAgent | None:
    return await db.get(SubAgent, sub_agent_id)
