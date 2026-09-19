import pytest
from httpx import ASGITransport, AsyncClient

from theshed.main import app


@pytest.mark.asyncio
async def test_api_prefix_reaches_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unprefixed = await client.get("/health")
        prefixed = await client.get("/api/health")
    assert unprefixed.status_code == 200
    assert prefixed.status_code == 200
    assert unprefixed.json() == prefixed.json() == {"status": "ok"}
