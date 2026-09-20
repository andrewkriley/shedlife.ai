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

from theshed.agents.registry import list_sub_agents
from theshed.db.models import SubAgentModelOverride
from theshed.debug import log as debug_log
from theshed.setup.providers import SUPPORTED

logger = logging.getLogger(__name__)

FALLBACK_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-5"],
    "openai": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
}


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


def pick_connection_setting(settings: list[SubAgentSetting]) -> SubAgentSetting | None:
    """The agent whose provider/model the header and chat should show."""
    if not settings:
        return None
    for setting in settings:
        if setting.id == "bootstrap.intake":
            return setting
    for setting in settings:
        if setting.overridden:
            return setting
    return settings[0]


async def list_sub_agent_settings(db: AsyncSession) -> list[SubAgentSetting]:
    sub_agents = await list_sub_agents(db)
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


def list_live_models(
    clients: dict[str, ModelListingClient | None],
) -> dict[str, list[str]]:
    """A real call to each cloud provider's own models-list API, per the
    spec. One provider's failure (an unset/invalid key, a network hiccup)
    doesn't take down the others — same fail-soft posture as Galileo
    tracing: an external provider's outage is never allowed to break a page
    that only needs to list two other providers' models. A missing client
    or a failed list falls back to a short known catalog so Settings can
    still offer Anthropic / OpenAI / Gemini."""
    result: dict[str, list[str]] = {}
    for provider in SUPPORTED:
        client = clients.get(provider)
        fallback = list(FALLBACK_MODELS.get(provider, []))
        if client is None:
            result[provider] = fallback
            continue
        debug_log.record("provider", "connect", f"Listing live models on {provider}")
        try:
            listed = [m.id for m in client.models.list()]
            result[provider] = listed or fallback
            debug_log.record(
                "provider",
                "connected",
                f"{provider} returned {len(listed)} models",
            )
        except Exception as exc:
            logger.exception("Listing models for provider %r failed", provider)
            debug_log.record(
                "provider",
                "error",
                f"{provider} models list failed: {exc}",
                level="error",
            )
            result[provider] = fallback
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
        debug_log.record(
            "settings",
            "assign",
            f"Cleared model override for {', '.join(sub_agent_ids)}",
            detail={"sub_agent_ids": sub_agent_ids},
        )
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
    debug_log.record(
        "settings",
        "assign",
        f"Assigned {provider}/{model} to {', '.join(sub_agent_ids)}",
        detail={"provider": provider, "model": model, "sub_agent_ids": sub_agent_ids},
    )
