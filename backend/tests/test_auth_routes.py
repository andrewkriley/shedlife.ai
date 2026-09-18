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

# Sync starlette TestClient runs the app in its own event loop (a separate
# BlockingPortal thread) — an asyncpg connection created by our async
# `db_session` fixture, on pytest-asyncio's loop, can't be used from there
# ("attached to a different loop"). httpx.AsyncClient against the ASGI app
# directly keeps everything on one loop. get_redis is overridden below, so
# the app's lifespan (which would otherwise create its own Redis client)
# doesn't need to run for these tests.


@pytest_asyncio.fixture
async def seeded_user(db_session: AsyncSession) -> dict[str, str]:
    # A distinct email from scripts/seed_dev_user.py's dev@example.com — that
    # one is committed for real by the dev-setup flow, outside this test's
    # rolled-back transaction, so reusing it would collide on the unique
    # (provider, provider_user_id) constraint.
    email = "test-auth-routes@example.com"
    user = User(display_name="Test User")
    db_session.add(user)
    await db_session.flush()
    identity = Identity(
        user_id=user.id,
        provider="local",
        provider_user_id=email,
        password_hash=hash_password("correct-horse-battery-staple"),
    )
    db_session.add(identity)
    await db_session.flush()
    return {"email": email, "password": "correct-horse-battery-staple"}


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestLogin:
    async def test_correct_credentials_returns_ok_and_sets_cookies(
        self, client: AsyncClient, seeded_user: dict[str, str]
    ) -> None:
        response = await client.post("/auth/login", json=seeded_user)

        assert response.status_code == 200
        assert "shed_session" in response.cookies
        assert "shed_csrf" in response.cookies

    async def test_wrong_password_returns_401(
        self, client: AsyncClient, seeded_user: dict[str, str]
    ) -> None:
        response = await client.post(
            "/auth/login", json={"email": seeded_user["email"], "password": "wrong"}
        )
        assert response.status_code == 401

    async def test_unknown_email_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_clears_cookies_and_invalidates_session(
        self, client: AsyncClient, seeded_user: dict[str, str]
    ) -> None:
        await client.post("/auth/login", json=seeded_user)

        response = await client.post("/auth/logout")

        assert response.status_code == 200
        assert client.cookies.get("shed_session") is None
