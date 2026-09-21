import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.auth.dependencies import get_redis
from theshed.auth.service import hash_password
from theshed.db.models import Identity, User
from theshed.db.session import get_session
from theshed.foundations.schema import PROXMOX_API_TOKEN_REF
from theshed.main import app
from theshed.probes.host import DefaultProbeHost
from theshed.secrets.client import LocalSecretsClient


def _inventory_http(url: str, _timeout: float, _headers=None) -> tuple[int, str]:
    if "/version" in url:
        return 200, json.dumps({"data": {"version": "8.3"}})
    if url.endswith("/nodes"):
        return 200, json.dumps({"data": [{"node": "pve", "maxcpu": 8, "maxmem": 0, "maxdisk": 0}]})
    if url.endswith("/network"):
        return 200, json.dumps({"data": [{"iface": "vmbr0", "type": "bridge"}]})
    if url.endswith("/storage"):
        return 200, json.dumps({"data": [{"storage": "local-lvm"}]})
    return 200, json.dumps({"data": {}})


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    app.state.redis = redis_client
    app.state.secrets = LocalSecretsClient()
    app.state.configure_llm = lambda *_args: None
    app.state.provider_live_check = None
    app.state.probe_host = DefaultProbeHost(
        secrets=app.state.secrets,
        http_get=_inventory_http,
        resolve=lambda _name: [],
        clock_offset=lambda: 0.0,
        proxmox_facts=lambda: {
            "nodes": ["pve"],
            "bridges": ["vmbr0"],
            "pools": ["local-lvm"],
            "vcpu": 8,
            "ram_gb": 32,
            "disk_gb": 200,
        },
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    email = "onboarding@example.com"
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
async def test_onboarding_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/onboarding/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_needed_on_a_fresh_store(client: AsyncClient, authed: dict[str, str]) -> None:
    response = await client.get("/onboarding/status")
    assert response.status_code == 200
    body = response.json()
    assert body["needed"] is True
    assert body["proxmox"]["api_token_set"] is False
    assert body["provider"]["api_key_set"] is False


@pytest.mark.asyncio
async def test_wizard_steps_and_summary(client: AsyncClient, authed: dict[str, str]) -> None:
    host = await client.post("/onboarding/proxmox", json={"host": "192.0.2.10"}, headers=authed)
    assert host.status_code == 200, host.text
    assert host.json()["proxmox"]["host"] == "192.0.2.10"

    token = await client.post(
        "/onboarding/proxmox",
        json={
            "api_token_id": "root@pam!shed",
            "api_token_secret": "secret-token",
            "discover": True,
        },
        headers=authed,
    )
    assert token.status_code == 200, token.text
    body = token.json()
    assert body["proxmox"]["api_token_set"] is True
    assert body["discovery"]["nodes"] == ["pve"]
    assert body["network"]["bridge"] == "vmbr0"
    assert "secret-token" not in token.text

    provider = await client.post(
        "/onboarding/provider",
        json={"provider": "anthropic", "api_key": "sk-ant-api03-testkey"},
        headers=authed,
    )
    assert provider.status_code == 200, provider.text
    assert provider.json()["provider"]["api_key_set"] is True

    tenant = await client.post(
        "/onboarding/tenant",
        json={"name": "Riley Lab", "slug": "riley-lab"},
        headers=authed,
    )
    assert tenant.status_code == 200
    assert tenant.json()["tenant"]["slug"] == "riley-lab"

    intent = await client.post("/onboarding/intent", json={"mode": "build"}, headers=authed)
    assert intent.status_code == 200
    assert intent.json()["intent"]["mode"] == "build"

    done = await client.post("/onboarding/complete", headers=authed)
    assert done.status_code == 200, done.text
    summary = done.json()
    assert summary["ok"] is True
    assert summary["needed"] is False
    ids = {item["id"] for item in summary["checks"]}
    assert "tenant" in ids
    assert "proxmox_api" in ids
    assert "llm_key" in ids


@pytest.mark.asyncio
async def test_adopt_without_urls_is_rejected(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    response = await client.post("/onboarding/intent", json={"mode": "adopt"}, headers=authed)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_existing_token_can_be_revalidated(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    app.state.secrets.set(PROXMOX_API_TOKEN_REF, "root@pam!shed=secret-token")
    await client.post("/onboarding/proxmox", json={"host": "192.0.2.10"}, headers=authed)
    response = await client.post("/onboarding/proxmox", json={"discover": True}, headers=authed)
    assert response.status_code == 200, response.text
    assert response.json()["proxmox"]["api_token_set"] is True


@pytest.mark.asyncio
async def test_provider_rejects_a_subscription(
    client: AsyncClient, authed: dict[str, str]
) -> None:
    response = await client.post(
        "/onboarding/provider",
        json={"provider": "anthropic", "api_key": "claude subscription"},
        headers=authed,
    )
    assert response.status_code == 400
    assert "subscription" in str(response.json()["detail"]).lower()
