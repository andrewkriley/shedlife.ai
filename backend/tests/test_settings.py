from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.models import SubAgent, SubAgentModelOverride, User
from theshed.db.session import get_session
from theshed.main import app
from theshed.secrets.client import LocalSecretsClient
from theshed.settings.service import (
    SubAgentSetting,
    list_live_models,
    list_sub_agent_settings,
    pick_connection_setting,
    resolved_runtime_choice,
    set_model_assignments,
)


@dataclass
class FakeModel:
    id: str


@dataclass
class FakeModelsList:
    items: list[FakeModel]

    def list(self) -> list[FakeModel]:
        return self.items


@dataclass
class FakeProviderClient:
    models: FakeModelsList
    vendor: str = "anthropic"


@pytest_asyncio.fixture
async def sub_agent(db_session: AsyncSession) -> SubAgent:
    agent = SubAgent(
        id="assist.test",
        macro_category="assist",
        description="Test agent",
        system_prompt="You help.",
        default_provider="anthropic",
        default_model="claude-haiku-4-5",
    )
    db_session.add(agent)
    await db_session.flush()
    return agent


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(display_name="Settings Test User")
    db_session.add(u)
    await db_session.flush()
    return u


@pytest.mark.asyncio
class TestListSubAgentSettings:
    async def test_uses_registry_default_when_no_override_exists(
        self, db_session: AsyncSession, sub_agent: SubAgent
    ) -> None:
        settings = await list_sub_agent_settings(db_session)

        setting = next(s for s in settings if s.id == sub_agent.id)
        assert setting.provider == "anthropic"
        assert setting.model == "claude-haiku-4-5"
        assert setting.overridden is False

    async def test_uses_override_when_one_exists(
        self, db_session: AsyncSession, sub_agent: SubAgent, user: User
    ) -> None:
        db_session.add(
            SubAgentModelOverride(
                sub_agent_id=sub_agent.id,
                provider="openai",
                model="gpt-5",
                set_by_user_id=user.id,
            )
        )
        await db_session.flush()

        settings = await list_sub_agent_settings(db_session)

        setting = next(s for s in settings if s.id == sub_agent.id)
        assert setting.provider == "openai"
        assert setting.model == "gpt-5"
        assert setting.overridden is True


class TestListLiveModels:
    def test_lists_models_per_provider(self) -> None:
        clients = {
            "anthropic": FakeProviderClient(FakeModelsList([FakeModel("claude-sonnet-5")])),
            "openai": FakeProviderClient(FakeModelsList([FakeModel("gpt-5")])),
        }

        result = list_live_models(clients)

        assert result["anthropic"] == ["claude-sonnet-5"]
        assert result["openai"] == ["gpt-5"]
        assert result["gemini"] == [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]

    def test_skips_a_missing_client_without_raising(self) -> None:
        clients = {
            "anthropic": None,
            "openai": FakeProviderClient(FakeModelsList([FakeModel("gpt-5")])),
        }

        result = list_live_models(clients)

        assert result["anthropic"] == [
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
        ]
        assert result["openai"] == ["gpt-5"]
        assert "gemini" in result

    def test_a_failing_provider_returns_an_empty_list_without_breaking_others(self) -> None:
        @dataclass
        class BrokenModels:
            def list(self) -> list[FakeModel]:
                raise RuntimeError("401 invalid credentials")

        @dataclass
        class BrokenClient:
            models: BrokenModels = field(default_factory=BrokenModels)

        clients = {
            "anthropic": FakeProviderClient(FakeModelsList([FakeModel("claude-sonnet-5")])),
            "openai": BrokenClient(),
        }

        result = list_live_models(clients)

        assert result["anthropic"] == ["claude-sonnet-5"]
        assert result["openai"] == ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"]


class TestPickConnectionSetting:
    def test_prefers_bootstrap_intake(self) -> None:
        other = SubAgentSetting(
            id="assist",
            macro_category="assist",
            description="",
            default_provider="anthropic",
            default_model="claude-haiku-4-5",
            provider="openai",
            model="gpt-4.1",
            overridden=True,
        )
        intake = SubAgentSetting(
            id="bootstrap.intake",
            macro_category="assist",
            description="",
            default_provider="openai",
            default_model="gpt-5.4",
            provider="openai",
            model="gpt-5.4-mini",
            overridden=True,
        )
        assert pick_connection_setting([other, intake]) is intake

    def test_falls_back_to_the_first_override(self) -> None:
        defaulted = SubAgentSetting(
            id="assist",
            macro_category="assist",
            description="",
            default_provider="anthropic",
            default_model="claude-haiku-4-5",
            provider="anthropic",
            model="claude-haiku-4-5",
            overridden=False,
        )
        overridden = SubAgentSetting(
            id="run.network",
            macro_category="run",
            description="",
            default_provider="anthropic",
            default_model="claude-haiku-4-5",
            provider="openai",
            model="gpt-5.4",
            overridden=True,
        )
        assert pick_connection_setting([defaulted, overridden]) is overridden

    def test_empty_list_is_none(self) -> None:
        assert pick_connection_setting([]) is None


@pytest.mark.asyncio
class TestResolvedRuntimeChoice:
    async def test_uses_a_matching_intake_override(
        self, db_session: AsyncSession, user: User
    ) -> None:
        await set_model_assignments(
            db=db_session,
            sub_agent_ids=["bootstrap.intake"],
            provider="openai",
            model="gpt-5",
            set_by_user_id=user.id,
        )

        provider, model = await resolved_runtime_choice(db_session, "openai")

        assert (provider, model) == ("openai", "gpt-5")

    async def test_does_not_send_a_claude_override_to_openai(
        self, db_session: AsyncSession, user: User
    ) -> None:
        await set_model_assignments(
            db=db_session,
            sub_agent_ids=["bootstrap.intake"],
            provider="anthropic",
            model="claude-haiku-4-5",
            set_by_user_id=user.id,
        )

        provider, model = await resolved_runtime_choice(db_session, "openai")

        assert (provider, model) == ("openai", "gpt-4.1-mini")


@pytest.mark.asyncio
class TestSetModelAssignments:
    async def test_creates_an_override_for_each_selected_sub_agent(
        self, db_session: AsyncSession, sub_agent: SubAgent, user: User
    ) -> None:
        await set_model_assignments(
            db=db_session,
            sub_agent_ids=[sub_agent.id],
            provider="openai",
            model="gpt-5",
            set_by_user_id=user.id,
        )

        settings = await list_sub_agent_settings(db_session)
        setting = next(s for s in settings if s.id == sub_agent.id)
        assert setting.provider == "openai"
        assert setting.model == "gpt-5"
        assert setting.overridden is True

    async def test_updates_an_existing_override_rather_than_duplicating_it(
        self, db_session: AsyncSession, sub_agent: SubAgent, user: User
    ) -> None:
        await set_model_assignments(
            db=db_session,
            sub_agent_ids=[sub_agent.id],
            provider="openai",
            model="gpt-5",
            set_by_user_id=user.id,
        )

        await set_model_assignments(
            db=db_session,
            sub_agent_ids=[sub_agent.id],
            provider="anthropic",
            model="claude-sonnet-5",
            set_by_user_id=user.id,
        )

        settings = await list_sub_agent_settings(db_session)
        setting = next(s for s in settings if s.id == sub_agent.id)
        assert setting.provider == "anthropic"
        assert setting.model == "claude-sonnet-5"

    async def test_clearing_reverts_to_the_registry_default(
        self, db_session: AsyncSession, sub_agent: SubAgent, user: User
    ) -> None:
        await set_model_assignments(
            db=db_session,
            sub_agent_ids=[sub_agent.id],
            provider="openai",
            model="gpt-5",
            set_by_user_id=user.id,
        )

        await set_model_assignments(
            db=db_session,
            sub_agent_ids=[sub_agent.id],
            provider=None,
            model=None,
            set_by_user_id=user.id,
        )

        settings = await list_sub_agent_settings(db_session)
        setting = next(s for s in settings if s.id == sub_agent.id)
        assert setting.overridden is False
        assert setting.provider == sub_agent.default_provider


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, user: User) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user_id] = lambda: str(user.id)
    app.dependency_overrides[require_csrf] = lambda: None
    app.state.llm_client = FakeProviderClient(FakeModelsList([FakeModel("claude-sonnet-5")]))
    app.state.openai_client = FakeProviderClient(FakeModelsList([FakeModel("gpt-5")]))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestSettingsRoutes:
    async def test_get_sub_agents_lists_registry_rows(
        self, client: AsyncClient, sub_agent: SubAgent
    ) -> None:
        response = await client.get("/settings/sub-agents")

        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert sub_agent.id in ids

    async def test_get_connection_reports_the_live_vendor_and_resolved_model(
        self, client: AsyncClient, sub_agent: SubAgent
    ) -> None:
        app.state.llm_client = FakeProviderClient(
            FakeModelsList([FakeModel("gpt-5.4")]), vendor="openai"
        )

        response = await client.get("/settings/connection")

        assert response.status_code == 200
        assert response.json() == {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "configured": True,
        }

    async def test_get_connection_uses_the_bootstrap_intake_override(
        self, client: AsyncClient, db_session: AsyncSession, user: User
    ) -> None:
        db_session.add(
            SubAgent(
                id="assist.other",
                macro_category="assist",
                description="Other",
                system_prompt="You help.",
                default_provider="anthropic",
                default_model="claude-haiku-4-5",
            )
        )
        await db_session.flush()
        await set_model_assignments(
            db=db_session,
            sub_agent_ids=["bootstrap.intake"],
            provider="openai",
            model="gpt-5.4-mini",
            set_by_user_id=user.id,
        )
        app.state.llm_client = FakeProviderClient(
            FakeModelsList([FakeModel("gpt-5.4-mini")]), vendor="openai"
        )

        response = await client.get("/settings/connection")

        assert response.status_code == 200
        assert response.json() == {
            "provider": "openai",
            "model": "gpt-5.4-mini",
            "configured": True,
        }

    async def test_get_connection_is_unconfigured_without_a_client(
        self, client: AsyncClient
    ) -> None:
        app.state.llm_client = None

        response = await client.get("/settings/connection")

        assert response.status_code == 200
        assert response.json() == {"provider": None, "model": None, "configured": False}

    async def test_get_models_returns_live_options_per_provider(self, client: AsyncClient) -> None:
        response = await client.get("/settings/models")

        assert response.status_code == 200
        assert response.json()["anthropic"] == ["claude-sonnet-5"]
        assert response.json()["openai"] == ["gpt-5"]
        assert "gemini" in response.json()

    async def test_get_models_keeps_openai_when_no_client_is_configured(
        self, client: AsyncClient
    ) -> None:
        app.state.openai_client = None

        response = await client.get("/settings/models")

        assert response.status_code == 200
        body = response.json()
        assert body["anthropic"] == ["claude-sonnet-5"]
        assert body["openai"] == ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"]
        assert body["gemini"] == ["gemini-2.5-flash", "gemini-2.5-pro"]

    async def test_post_model_assignments_applies_and_returns_updated_settings(
        self, client: AsyncClient
    ) -> None:
        app.state.llm_client = FakeProviderClient(
            FakeModelsList([FakeModel("gpt-5")]), vendor="openai"
        )
        app.state.classifier_model = "gpt-4.1-mini"
        response = await client.post(
            "/settings/model-assignments",
            json={
                "sub_agent_ids": ["bootstrap.intake"],
                "provider": "openai",
                "model": "gpt-5",
            },
        )

        assert response.status_code == 200
        setting = next(row for row in response.json() if row["id"] == "bootstrap.intake")
        assert setting["provider"] == "openai"
        assert setting["model"] == "gpt-5"
        assert setting["overridden"] is True
        assert app.state.classifier_model == "gpt-5"

    async def test_post_model_assignments_rejects_a_vendor_that_is_not_live(
        self, client: AsyncClient
    ) -> None:
        app.state.llm_client = FakeProviderClient(
            FakeModelsList([FakeModel("gpt-5")]), vendor="openai"
        )
        app.state.classifier_model = "gpt-4.1-mini"

        response = await client.post(
            "/settings/model-assignments",
            json={
                "sub_agent_ids": ["bootstrap.intake"],
                "provider": "anthropic",
                "model": "claude-haiku-4-5",
            },
        )

        assert response.status_code == 400
        assert "openai" in response.json()["detail"]
        assert "anthropic" in response.json()["detail"]
        assert app.state.classifier_model == "gpt-4.1-mini"

    async def test_post_provider_key_configures_the_openai_client(
        self, client: AsyncClient
    ) -> None:
        configured: list[tuple[str, str]] = []
        app.state.secrets = LocalSecretsClient()
        app.state.configure_llm = lambda provider, key: configured.append((provider, key))
        app.state.provider_live_check = None

        response = await client.post(
            "/settings/provider",
            json={"provider": "openai", "api_key": "sk-test-openai"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "provider": "openai"}
        assert configured == [("openai", "sk-test-openai")]
        assert app.state.secrets.get("local://providers/llm/vendor") == "openai"

    async def test_post_model_assignments_with_no_provider_clears_the_override(
        self, client: AsyncClient, sub_agent: SubAgent
    ) -> None:
        app.state.llm_client = FakeProviderClient(
            FakeModelsList([FakeModel("claude-sonnet-5")]), vendor="anthropic"
        )
        await client.post(
            "/settings/model-assignments",
            json={
                "sub_agent_ids": [sub_agent.id],
                "provider": "anthropic",
                "model": "claude-sonnet-5",
            },
        )

        response = await client.post(
            "/settings/model-assignments",
            json={"sub_agent_ids": [sub_agent.id]},
        )

        assert response.status_code == 200
        setting = next(row for row in response.json() if row["id"] == sub_agent.id)
        assert setting["overridden"] is False

    async def test_get_galileo_settings_returns_defaults(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GALILEO_API_KEY", raising=False)
        monkeypatch.delenv("GALILEO_CONSOLE_URL", raising=False)
        monkeypatch.delenv("GALILEO_PROJECT", raising=False)
        monkeypatch.delenv("GALILEO_PROJECT_NAME", raising=False)
        monkeypatch.delenv("GALILEO_LOG_STREAM", raising=False)
        app.state.secrets = LocalSecretsClient()

        response = await client.get("/settings/galileo")

        assert response.status_code == 200
        body = response.json()
        assert body["project"] == "the-shed"
        assert body["log_stream"] == "default"
        assert body["host"] == ""
        assert body["api_key_set"] is False
        assert body["configured"] is False

    async def test_post_galileo_settings_saves_and_hides_the_key(
        self, client: AsyncClient
    ) -> None:
        app.state.secrets = LocalSecretsClient()

        response = await client.post(
            "/settings/galileo",
            json={
                "project": "shed-lab",
                "host": "https://galileo.example.test",
                "log_stream": "bootstrap",
                "api_key": "galileo-secret",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "project": "shed-lab",
            "host": "https://galileo.example.test",
            "log_stream": "bootstrap",
            "api_key_set": True,
            "configured": True,
        }
        assert "galileo-secret" not in str(body)
        tracer = app.state.tracer_factory()
        assert tracer._project == "shed-lab"
        assert tracer._log_stream == "bootstrap"

        again = await client.get("/settings/galileo")
        assert again.json()["api_key_set"] is True
        assert "galileo-secret" not in again.text


@pytest.mark.asyncio
class TestSettingsRoutesRequireAuth:
    async def test_sub_agents_requires_authentication(self, db_session: AsyncSession) -> None:
        app.dependency_overrides[get_session] = lambda: db_session
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/settings/sub-agents")
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()
