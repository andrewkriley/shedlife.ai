import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.registry import get_sub_agent, list_sub_agents


@pytest.mark.asyncio
class TestRegistry:
    async def test_list_sub_agents_includes_seeded_assist(self, db_session: AsyncSession) -> None:
        sub_agents = await list_sub_agents(db_session)
        ids = {sa.id for sa in sub_agents}
        assert "assist" in ids

    async def test_get_sub_agent_returns_matching_row(self, db_session: AsyncSession) -> None:
        sub_agent = await get_sub_agent(db_session, "assist")
        assert sub_agent is not None
        assert sub_agent.macro_category == "assist"
        assert sub_agent.default_provider == "anthropic"

    async def test_get_sub_agent_returns_none_for_unknown_id(self, db_session: AsyncSession) -> None:
        assert await get_sub_agent(db_session, "does.not.exist") is None
