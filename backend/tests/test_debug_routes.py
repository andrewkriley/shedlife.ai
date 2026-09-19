import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from theshed.debug import log as debug_log
from theshed.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    debug_log.reset_for_tests()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    debug_log.reset_for_tests()


@pytest.mark.asyncio
async def test_debug_starts_off_and_toggle_enables_logs(client: AsyncClient) -> None:
    status = await client.get("/debug/status")
    assert status.json() == {"enabled": False}

    await client.post("/debug/enabled", json={"enabled": True})
    assert (await client.get("/debug/status")).json()["enabled"] is True

    await client.post(
        "/debug/events",
        json={"event": "click", "message": "Clicked Save schema", "detail": {"name": "Save schema"}},
    )
    logs = await client.get("/debug/logs")
    body = logs.json()
    assert body["enabled"] is True
    assert any(event["event"] == "click" for event in body["events"])


@pytest.mark.asyncio
async def test_http_errors_are_recorded_when_debug_on(client: AsyncClient) -> None:
    await client.post("/debug/enabled", json={"enabled": True})
    await client.get("/no-such-route")
    messages = [event["message"] for event in (await client.get("/debug/logs")).json()["events"]]
    assert any("GET /no-such-route" in message and "404" in message for message in messages)
