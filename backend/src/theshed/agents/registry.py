"""Sub-agent registry lookups, per docs/spec/core-agentic-loop.md. Thin on
purpose — the registry itself is just the `sub_agents` table; this module
exists so callers don't hand-write the same queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.db.models import SubAgent
from theshed.profile import BOOTSTRAP_SUB_AGENT_ID, is_bootstrap_profile


async def list_sub_agents(db: AsyncSession) -> list[SubAgent]:
    result = await db.execute(select(SubAgent))
    agents = list(result.scalars().all())
    if is_bootstrap_profile():
        return [sa for sa in agents if sa.id == BOOTSTRAP_SUB_AGENT_ID]
    return agents


async def get_sub_agent(db: AsyncSession, sub_agent_id: str) -> SubAgent | None:
    return await db.get(SubAgent, sub_agent_id)
