"""Integration-level coverage for the pause-for-approval path: a real
Postgres session, a real stream_turn -> PendingTurnApproval -> resume_turn
round trip, only the LLM mocked. Nothing in the live registry has a
has_side_effects tool yet (assist's tools are both server-executed), so
this is the only way this path is exercised at all before run.network
exists — same situation synthesis.py was in before today."""

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from theshed.agents.providers.anthropic import LLMResponse
from theshed.agents.tool_loop import ToolCall
from theshed.auth.dependencies import get_current_user_id, require_csrf
from theshed.db.models import PendingTurnApproval, SubAgent, Turn, TurnSubAgentResult, User
from theshed.db.session import get_session
from theshed.main import app
from theshed.observability.galileo import TurnTracer
from theshed.turns.service import resume_turn, stream_turn


@dataclass
class ScriptedLLM:
    responses: list[LLMResponse]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "model": model, "tools": tools})
        return self.responses[len(self.calls) - 1]


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(display_name="Approvals Test User")
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def risky_sub_agent(db_session: AsyncSession) -> SubAgent:
    sub_agent = SubAgent(
        id="run.network",
        macro_category="run",
        description="Network operations, including ones that change live config.",
        system_prompt="You manage the network.",
        tools=[{"name": "confirm_create_firewall_policy", "has_side_effects": True}],
        default_provider="anthropic",
        default_model="claude-sonnet-5",
    )
    db_session.add(sub_agent)
    await db_session.flush()
    return sub_agent


def _classify_response(sub_agent: SubAgent) -> LLMResponse:
    return LLMResponse(
        text=json.dumps(
            [{"macro_category": sub_agent.macro_category, "sub_agent_id": sub_agent.id}]
        ),
        tool_calls=[],
        stop_reason="end_turn",
    )


@pytest.mark.asyncio
class TestPauseAndResume:
    async def test_a_side_effect_tool_call_pauses_the_turn_and_persists_state(
        self, db_session: AsyncSession, user: User, risky_sub_agent: SubAgent
    ) -> None:
        llm = ScriptedLLM(
            [
                _classify_response(risky_sub_agent),
                LLMResponse(
                    text=None,
                    tool_calls=[
                        {
                            "id": "tu_1",
                            "name": "confirm_create_firewall_policy",
                            "arguments": {"rule": "block all"},
                        }
                    ],
                    stop_reason="tool_use",
                ),
            ]
        )

        events = [
            event
            async for event in stream_turn(
                db=db_session,
                user_id=user.id,
                conversation_id=None,
                message="lock down the network",
                llm=llm,
                classifier_model="claude-haiku-4-5",
                tracer=TurnTracer(None),
            )
        ]

        assert events[-1]["event"] == "approval_required"

        payload = json.loads(events[-1]["data"])
        assert payload["tool_name"] == "confirm_create_firewall_policy"
        assert payload["arguments"] == {"rule": "block all"}
        assert payload["sub_agent_id"] == "run.network"

        turn_id = payload["turn_id"]
        pending = await db_session.get(PendingTurnApproval, turn_id)
        assert pending is not None
        assert pending.tool_use_id == "tu_1"
        assert pending.remaining_sub_agent_ids == []
        assert pending.completed_results == {}

        turn = await db_session.get(Turn, turn_id)
        assert turn is not None
        assert turn.final_response is None  # not finalized yet — still paused

    async def test_approving_resumes_and_completes_the_turn(
        self, db_session: AsyncSession, user: User, risky_sub_agent: SubAgent
    ) -> None:
        llm = ScriptedLLM(
            [
                _classify_response(risky_sub_agent),
                LLMResponse(
                    text=None,
                    tool_calls=[
                        {
                            "id": "tu_1",
                            "name": "confirm_create_firewall_policy",
                            "arguments": {"rule": "block all"},
                        }
                    ],
                    stop_reason="tool_use",
                ),
            ]
        )
        events = [
            e
            async for e in stream_turn(
                db=db_session,
                user_id=user.id,
                conversation_id=None,
                message="lock down the network",
                llm=llm,
                classifier_model="claude-haiku-4-5",
                tracer=TurnTracer(None),
            )
        ]

        turn_id = json.loads(events[-1]["data"])["turn_id"]
        pending = await db_session.get(PendingTurnApproval, turn_id)
        assert pending is not None

        # Nothing in the live registry has a real client-side tool executor
        # yet (see the module docstring), so this stands one up just for the
        # test — proving the whole pause -> approve -> execute -> resume ->
        # complete cycle actually works, not just up to the executor boundary.
        llm.responses.append(
            LLMResponse(text="Done — the policy is live.", tool_calls=[], stop_reason="end_turn")
        )

        async def fake_executor(call: ToolCall) -> str:
            assert call.tool_name == "confirm_create_firewall_policy"
            assert call.arguments == {"rule": "block all"}
            return "policy created"

        resume_events = [
            e
            async for e in resume_turn(
                db=db_session,
                pending=pending,
                approved=True,
                llm=llm,
                classifier_model="claude-haiku-4-5",
                tracer=TurnTracer(None),
                tool_executor=fake_executor,
            )
        ]

        assert resume_events[-1]["event"] == "done"
        token_events = [json.loads(e["data"])["text"] for e in resume_events if e["event"] == "token"]
        assert "".join(token_events) == "Done — the policy is live."

        turn = await db_session.get(Turn, turn_id)
        assert turn is not None
        assert turn.final_response == "Done — the policy is live."
        assert await db_session.get(PendingTurnApproval, turn_id) is None

        result = (
            await db_session.execute(
                select(TurnSubAgentResult).where(TurnSubAgentResult.turn_id == turn_id)
            )
        ).scalar_one()
        assert result.status_code == 0
        assert result.result == "Done — the policy is live."

    async def test_declining_ends_the_turn_without_executing_the_tool(
        self, db_session: AsyncSession, user: User, risky_sub_agent: SubAgent
    ) -> None:
        llm = ScriptedLLM(
            [
                _classify_response(risky_sub_agent),
                LLMResponse(
                    text=None,
                    tool_calls=[
                        {
                            "id": "tu_1",
                            "name": "confirm_create_firewall_policy",
                            "arguments": {"rule": "block all"},
                        }
                    ],
                    stop_reason="tool_use",
                ),
            ]
        )
        events = [
            e
            async for e in stream_turn(
                db=db_session,
                user_id=user.id,
                conversation_id=None,
                message="lock down the network",
                llm=llm,
                classifier_model="claude-haiku-4-5",
                tracer=TurnTracer(None),
            )
        ]

        turn_id = json.loads(events[-1]["data"])["turn_id"]
        pending = await db_session.get(PendingTurnApproval, turn_id)
        assert pending is not None

        resume_events = [
            e
            async for e in resume_turn(
                db=db_session,
                pending=pending,
                approved=False,
                llm=llm,
                classifier_model="claude-haiku-4-5",
                tracer=TurnTracer(None),
            )
        ]

        assert resume_events[-1]["event"] == "done"
        turn = await db_session.get(Turn, turn_id)
        assert turn is not None
        assert turn.final_response is not None
        assert "declined" in turn.final_response.lower()

        # The pending row is cleared either way.
        assert await db_session.get(PendingTurnApproval, turn_id) is None

        # No extra LLM call happened (declining ends the loop, per spec —
        # no further model call): still exactly the 2 scripted calls from
        # the initial stream_turn.
        assert len(llm.calls) == 2

        result = (
            await db_session.execute(
                select(TurnSubAgentResult).where(TurnSubAgentResult.turn_id == turn_id)
            )
        ).scalar_one()
        assert result.status_code == 1


@pytest_asyncio.fixture
async def approvals_client(db_session: AsyncSession, user: User) -> AsyncClient:
    # SSE happy-path streaming isn't route-tested elsewhere either
    # (submit_turn has no route test) — that's covered live, in a browser.
    # This client exists only to prove the 404 case wires up correctly.
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user_id] = lambda: str(user.id)
    app.dependency_overrides[require_csrf] = lambda: None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestApprovalsRoute:
    async def test_returns_404_when_theres_no_pending_approval(
        self, approvals_client: AsyncClient
    ) -> None:
        response = await approvals_client.post(
            f"/turns/{uuid4()}/approvals", json={"approved": True}
        )

        assert response.status_code == 404
