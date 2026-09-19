from dataclasses import dataclass
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
from theshed.main import app
from theshed.observability.galileo import TurnTracer
from theshed.turns.service import verify_turn


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
    explicit flush(), which nothing ever called. This spy exists to make
    "flush happened at the point a trace actually concludes" a assertable
    fact instead of something only a live Galileo dashboard check reveals."""

    def __init__(self) -> None:
        super().__init__(None)
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


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
        assert tracer.flush_count == 1

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
