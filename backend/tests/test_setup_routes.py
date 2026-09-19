import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_redis
from theshed.auth.service import hash_password
from theshed.db.models import Identity, User
from theshed.db.session import get_session
from theshed.main import app
from theshed.secrets.client import LocalSecretsClient


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    app.state.secrets = LocalSecretsClient()
    app.state.configure_llm = lambda *_args: None
    app.state.provider_live_check = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_setup_status_needed_when_no_identities(client: AsyncClient) -> None:
    response = await client.get("/setup/status")
    assert response.status_code == 200
    assert response.json() == {"needed": True}


@pytest.mark.asyncio
async def test_setup_creates_user_and_local_secret(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/setup",
        json={
            "email": "op@example.com",
            "password": "correct-horse-battery-staple",
            "provider": "anthropic",
            "api_key": "sk-ant-api03-testkey",
        },
    )
    assert response.status_code == 200
    assert "shed_session" in response.cookies
    assert app.state.secrets.get("local://providers/llm/api_key") == "sk-ant-api03-testkey"


@pytest.mark.asyncio
async def test_setup_rejects_subscription(client: AsyncClient) -> None:
    response = await client.post(
        "/setup",
        json={
            "email": "op@example.com",
            "password": "correct-horse-battery-staple",
            "provider": "anthropic",
            "api_key": "claude subscription",
        },
    )
    assert response.status_code == 400
    assert "subscription" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_setup_refused_once_an_identity_exists(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(display_name="Existing")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Identity(
            user_id=user.id,
            provider="local",
            provider_user_id="already@example.com",
            password_hash=hash_password("x"),
        )
    )
    await db_session.flush()

    response = await client.post(
        "/setup",
        json={
            "email": "op@example.com",
            "password": "correct-horse-battery-staple",
            "provider": "anthropic",
            "api_key": "sk-ant-api03-testkey",
        },
    )
    assert response.status_code == 409
