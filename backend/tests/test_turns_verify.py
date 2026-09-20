from dataclasses import dataclass
from types import TracebackType
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.providers.anthropic import LLMResponse
from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.models import Conversation, Turn, User
from theshed.db.session import get_session
from theshed.debug import log as debug_log
from theshed.main import app
from theshed.observability.galileo import TurnTracer
from theshed.turns.service import public_turn_error, stream_turn, verify_turn


@dataclass
class FakeLLM:
    response_text: str | None

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        return LLMResponse(text=self.response_text, tool_calls=[], stop_reason="end_turn")


class SpyTracer(TurnTracer):
    """Confirmed live: a session with no traces or spans in it despite no
    errors anywhere — GalileoLogger batches locally and only uploads on an
    explicit flush(). TurnTracer now flushes automatically on `__exit__`
    (galileo_context's own exit does it) — this spy counts exits, making
    "the tracer's context was actually closed" an assertable fact instead
    of something only a live Galileo dashboard check reveals."""

    def __init__(self) -> None:
        super().__init__(None)
        self.exit_count = 0

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_count += 1
        super().__exit__(exc_type, exc_value, traceback)


@pytest_asyncio.fixture
async def completed_turn(db_session: AsyncSession) -> Turn:
    user = User(display_name="Verify Test User")
    db_session.add(user)
    await db_session.flush()
    conversation = Conversation(user_id=user.id)
    db_session.add(conversation)
    await db_session.flush()
    turn = Turn(
        conversation_id=conversation.id,
        user_message="What's the capital of France?",
        final_response="Paris.",
    )
    db_session.add(turn)
    await db_session.flush()
    return turn


@pytest.mark.asyncio
class TestVerifyTurnService:
    async def test_stores_and_returns_the_verifiers_assessment(
        self, db_session: AsyncSession, completed_turn: Turn
    ) -> None:
        llm = FakeLLM(response_text="This holds up — it directly answers the question.")
        conversation = await db_session.get(Conversation, completed_turn.conversation_id)
        assert conversation is not None
        tracer = SpyTracer()

        verification = await verify_turn(
            db=db_session,
            turn_id=completed_turn.id,
            user_id=conversation.user_id,
            llm=llm,
            verifier_model="claude-sonnet-5",
            tracer=tracer,
        )

        assert verification is not None
        assert verification.result == "This holds up — it directly answers the question."
        assert verification.turn_id == completed_turn.id
        assert tracer.exit_count == 1

    async def test_returns_none_for_an_unknown_turn(self, db_session: AsyncSession) -> None:
        result = await verify_turn(
            db=db_session,
            turn_id=uuid4(),
            user_id=uuid4(),
            llm=FakeLLM(response_text="ok"),
            verifier_model="claude-sonnet-5",
            tracer=TurnTracer(None),
        )

        assert result is None

    async def test_returns_none_for_a_turn_with_no_final_response_yet(
        self, db_session: AsyncSession
    ) -> None:
        user = User(display_name="In-flight Turn User")
        db_session.add(user)
        await db_session.flush()
        conversation = Conversation(user_id=user.id)
        db_session.add(conversation)
        await db_session.flush()
        turn = Turn(conversation_id=conversation.id, user_message="still working on it")
        db_session.add(turn)
        await db_session.flush()

        result = await verify_turn(
            db=db_session,
            turn_id=turn.id,
            user_id=user.id,
            llm=FakeLLM(response_text="ok"),
            verifier_model="claude-sonnet-5",
            tracer=TurnTracer(None),
        )

        assert result is None


@pytest_asyncio.fixture
async def route_user(db_session: AsyncSession) -> User:
    user = User(display_name="Route Test User")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, route_user: User) -> AsyncClient:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user_id] = lambda: str(route_user.id)
    app.dependency_overrides[require_csrf] = lambda: None
    app.state.llm_client = FakeLLM(response_text="Looks correct to me.")
    app.state.classifier_model = "claude-sonnet-5"
    app.state.tracer_factory = lambda: TurnTracer(None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def completed_turn_for_route(db_session: AsyncSession, route_user: User) -> Turn:
    # Owned by `route_user` — the same user `client` authenticates as — so the
    # FK on turn_verifications.invoked_by_user_id is satisfied once the route
    # actually inserts a verification row.
    conversation = Conversation(user_id=route_user.id)
    db_session.add(conversation)
    await db_session.flush()
    turn = Turn(
        conversation_id=conversation.id,
        user_message="What's the capital of France?",
        final_response="Paris.",
    )
    db_session.add(turn)
    await db_session.flush()
    return turn


@pytest.mark.asyncio
class TestVerifyTurnRoute:
    async def test_returns_the_assessment_for_a_completed_turn(
        self, client: AsyncClient, completed_turn_for_route: Turn
    ) -> None:
        response = await client.post(f"/turns/{completed_turn_for_route.id}/verify")

        assert response.status_code == 200
        assert response.json() == {"result": "Looks correct to me."}

    async def test_returns_404_for_an_unknown_turn(self, client: AsyncClient) -> None:
        response = await client.post(f"/turns/{uuid4()}/verify")

        assert response.status_code == 404


def test_public_turn_error_prefers_vendor_message() -> None:
    class VendorError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("Error code: 400 - buried dump")
            self.body = {
                "error": {
                    "message": (
                        "Unsupported value: 'reasoning_effort' does not support "
                        "'none' with this model."
                    ),
                    "type": "invalid_request_error",
                }
            }

    assert public_turn_error(VendorError()) == (
        "The assistant could not answer: Unsupported value: 'reasoning_effort' "
        "does not support 'none' with this model."
    )


def test_public_turn_error_falls_back_to_str() -> None:
    assert public_turn_error(RuntimeError("timeout")) == (
        "The assistant could not answer: timeout"
    )


@pytest.mark.asyncio
async def test_stream_turn_reports_a_missing_llm_client(
    db_session: AsyncSession, route_user: User
) -> None:
    events = [
        event
        async for event in stream_turn(
            db=db_session,
            user_id=route_user.id,
            conversation_id=None,
            message="hello",
            llm=None,
            classifier_model="claude-haiku-4-5",
            tracer=TurnTracer(None),
        )
    ]
    assert any("No LLM client" in event.get("data", "") for event in events)


@pytest.mark.asyncio
async def test_stream_turn_records_debug_events_when_debug_is_on(
    db_session: AsyncSession, route_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THESHED_DEBUG", "1")
    debug_log.reset_for_tests()
    events = [
        event
        async for event in stream_turn(
            db=db_session,
            user_id=route_user.id,
            conversation_id=None,
            message="hello",
            llm=None,
            classifier_model="claude-haiku-4-5",
            tracer=TurnTracer(None),
        )
    ]
    assert any("No LLM client" in event.get("data", "") for event in events)
    logged = debug_log.snapshot()
    assert any(item["source"] == "turn" and item["event"] == "start" for item in logged)
    assert any(item["source"] == "turn" and item["event"] == "error" for item in logged)
