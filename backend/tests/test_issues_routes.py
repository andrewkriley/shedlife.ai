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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    email = "issues-routes@example.com"
    user = User(display_name="Op")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Identity(
            user_id=user.id,
            provider="local",
            provider_user_id=email,
            password_hash=hash_password("correct-horse-battery-staple"),
        )
    )
    await db_session.flush()
    response = await client.post(
        "/auth/login", json={"email": email, "password": "correct-horse-battery-staple"}
    )
    assert response.status_code == 200
    csrf = client.cookies.get("shed_csrf")
    assert csrf
    return {"x-csrf-token": csrf}


@pytest.mark.asyncio
async def test_operator_can_file_and_list_issues(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    created = await client.post(
        "/issues",
        json={
            "summary": "UI showed a 500",
            "detail": "socket timeout talking to the host",
            "classification": "environment",
        },
        headers=authed,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["source"] == "operator"
    assert body["classification"] == "environment"
    assert "sk-ant" not in body["detail"]

    listed = await client.get("/issues")
    assert listed.status_code == 200
    assert listed.json()[0]["summary"] == "UI showed a 500"


@pytest.mark.asyncio
async def test_file_upstream_is_not_implemented(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    created = await client.post(
        "/issues",
        json={"summary": "product exploded", "detail": "unhandled 5xx", "classification": "product-bug"},
        headers=authed,
    )
    issue_id = created.json()["id"]
    response = await client.post(f"/issues/{issue_id}/file-upstream", headers=authed)
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_redacts_secrets_in_operator_filings(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    created = await client.post(
        "/issues",
        json={
            "summary": "pasted a key",
            "detail": "used sk-ant-api03-abcdefghijklmnopqrstuvwxyz by mistake",
        },
        headers=authed,
    )
    assert "[redacted]" in created.json()["detail"]
    assert "sk-ant-api03" not in created.json()["detail"]
