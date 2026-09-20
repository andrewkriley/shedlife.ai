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

    async def test_assist_has_web_search_and_code_execution_tools(
        self, db_session: AsyncSession
    ) -> None:
        sub_agent = await get_sub_agent(db_session, "assist")
        assert sub_agent is not None
        tool_names = {t["name"] for t in sub_agent.tools}
        assert tool_names == {"web_search", "code_execution"}
        assert all(t["has_side_effects"] is False for t in sub_agent.tools)

    async def test_bootstrap_intake_is_seeded(self, db_session: AsyncSession) -> None:
        sub_agent = await get_sub_agent(db_session, "bootstrap.intake")
        assert sub_agent is not None
        assert sub_agent.macro_category == "assist"
        assert sub_agent.default_provider == "openai"
        assert sub_agent.default_model == "gpt-4.1-mini"
        tool_names = {t["name"] for t in sub_agent.tools}
        assert "foundations_write" in tool_names
        assert "install_ssh_key" in tool_names

    async def test_bootstrap_profile_lists_only_intake(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("THESHED_PROFILE", "bootstrap")
        ids = {sa.id for sa in await list_sub_agents(db_session)}
        assert ids == {"bootstrap.intake"}
