import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_redis
from theshed.auth.service import hash_password
from theshed.db.models import Identity, User
from theshed.db.session import get_session
from theshed.foundations.schema import empty_foundations
from theshed.main import app
from theshed.probes.host import DefaultProbeHost
from theshed.probes.runner import ProbeResult
from theshed.secrets.client import LocalSecretsClient


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    app.state.redis = redis_client
    app.state.secrets = LocalSecretsClient()
    app.state.probe_host = DefaultProbeHost(
        secrets=app.state.secrets,
        http_get=lambda _url, _timeout: (200, ""),
        resolve=lambda _name: [],
        clock_offset=lambda: 0.0,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    email = "foundations-routes@example.com"
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
async def test_foundations_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/foundations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_get_validate_and_export(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    doc = empty_foundations()
    doc["tenant"] = {"name": "Riley Lab", "slug": "riley-lab"}
    doc["operator"] = {"email": "op@example.com"}
    doc["proxmox"] = {
        "host": "192.0.2.10",
        "node": "pve",
        "api_token_id": "root@pam!shed",
        "api_token_secret": "secret-token",
        "ssh_key_fingerprint": None,
    }

    put = await client.put("/foundations", json={"document": doc}, headers=authed)
    assert put.status_code == 200
    assert put.json()["tenant"]["slug"] == "riley-lab"

    got = await client.get("/foundations")
    assert got.status_code == 200
    assert got.json()["tenant"]["name"] == "Riley Lab"

    validated = await client.post("/foundations/validate", headers=authed)
    assert validated.status_code == 200
    body = validated.json()
    assert body["ok"] is True
    assert body["errors"] == {}

    exported = await client.get("/foundations/export")
    assert exported.status_code == 200
    yaml_text = exported.json()["yaml"]
    assert "riley-lab" in yaml_text
    assert "sk-ant" not in yaml_text
    assert "secret-token" not in yaml_text
    assert "local://proxmox/api_token" in yaml_text
    stored = await client.get("/foundations")
    assert stored.json()["proxmox"]["api_token_set"] is True
    assert stored.json()["proxmox"]["api_token_id"] == "root@pam!shed"
    assert "api_token" not in stored.json()["proxmox"] or stored.json()["proxmox"].get(
        "api_token"
    ) in {None, ""}
    assert stored.json()["proxmox"].get("api_token_secret") in {None, ""}


@pytest.mark.asyncio
async def test_validate_failures_are_not_issues(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    await client.put("/foundations", json={"document": empty_foundations()}, headers=authed)
    validated = await client.post("/foundations/validate", headers=authed)
    assert validated.json()["ok"] is False
    issues = await client.get("/issues")
    assert issues.status_code == 200
    assert issues.json() == []


@pytest.mark.asyncio
async def test_probe_persists_and_crashes_open_an_issue(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    app.state.secrets.set("local://providers/llm/api_key", "sk-ant-api03-test")
    ran = await client.post("/probes/llm_key", headers=authed)
    assert ran.status_code == 200
    assert ran.json()["status"] == "pass"

    stored = await client.get("/foundations")
    assert stored.json()["probes"]["llm_key"]["status"] == "pass"

    blocked = await client.post("/probes/ssh_key_installed", headers=authed)
    assert blocked.status_code == 409

    class BoomHost:
        def outbound_https(self) -> ProbeResult:
            raise RuntimeError("socket closed")

    app.state.probe_host = BoomHost()
    crashed = await client.post("/probes/outbound_https", headers=authed)
    assert crashed.status_code == 200
    assert crashed.json()["status"] == "error"
    issues = await client.get("/issues")
    assert any("outbound_https" in issue["summary"] for issue in issues.json())
