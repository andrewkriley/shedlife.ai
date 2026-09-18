"""Settings surface, per docs/spec/core-agentic-loop.md ("Interfaces" —
Settings surface) and its "Provider/model overrides" Data section.

`sub_agent_model_overrides` holds at most one row per sub-agent; absence of
a row means "use the registry default." Provider resolution (in
agents/orchestrator.py, a later concern) checks this table first.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.db.models import SubAgent, SubAgentModelOverride

logger = logging.getLogger(__name__)


class ModelListingClient(Protocol):
    """Both anthropic.Anthropic and openai.OpenAI satisfy this shape:
    `.models.list()` returning an iterable of objects with an `.id`."""

    models: Any


@dataclass
class SubAgentSetting:
    id: str
    macro_category: str
    description: str
    default_provider: str
    default_model: str
    provider: str
    model: str
    overridden: bool


async def list_sub_agent_settings(db: AsyncSession) -> list[SubAgentSetting]:
    sub_agents = (await db.execute(select(SubAgent))).scalars().all()
    overrides = {
        o.sub_agent_id: o for o in (await db.execute(select(SubAgentModelOverride))).scalars().all()
    }
    return [
        SubAgentSetting(
            id=sa.id,
            macro_category=sa.macro_category,
            description=sa.description,
            default_provider=sa.default_provider,
            default_model=sa.default_model,
            provider=overrides[sa.id].provider if sa.id in overrides else sa.default_provider,
            model=overrides[sa.id].model if sa.id in overrides else sa.default_model,
            overridden=sa.id in overrides,
        )
        for sa in sub_agents
    ]


def list_live_models(clients: dict[str, ModelListingClient]) -> dict[str, list[str]]:
    """A real call to each cloud provider's own models-list API, per the
    spec. One provider's failure (an unset/invalid key, a network hiccup)
    doesn't take down the others — same fail-soft posture as Galileo
    tracing: an external provider's outage is never allowed to break a page
    that only needs to list two other providers' models."""
    result: dict[str, list[str]] = {}
    for provider, client in clients.items():
        try:
            result[provider] = [m.id for m in client.models.list()]
        except Exception:
            logger.exception("Listing models for provider %r failed", provider)
            result[provider] = []
    return result


async def set_model_assignments(
    db: AsyncSession,
    sub_agent_ids: list[str],
    provider: str | None,
    model: str | None,
    set_by_user_id: uuid.UUID,
) -> None:
    """provider/model both set: upsert an override for each id. Either left
    unset (None): clear the override, reverting those sub-agents to their
    registry default — the "absence of a row" case from the Data section."""
    if provider is None or model is None:
        for sub_agent_id in sub_agent_ids:
            existing = await db.get(SubAgentModelOverride, sub_agent_id)
            if existing is not None:
                await db.delete(existing)
        await db.commit()
        return

    for sub_agent_id in sub_agent_ids:
        existing = await db.get(SubAgentModelOverride, sub_agent_id)
        if existing is not None:
            existing.provider = provider
            existing.model = model
            existing.set_by_user_id = set_by_user_id
            existing.set_at = datetime.now(UTC)
        else:
            db.add(
                SubAgentModelOverride(
                    sub_agent_id=sub_agent_id,
                    provider=provider,
                    model=model,
                    set_by_user_id=set_by_user_id,
                )
            )
    await db.commit()
