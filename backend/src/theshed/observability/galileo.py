"""Galileo tracing, per docs/architecture.md and docs/spec/core-agentic-loop.md:
one Galileo session per conversation, one trace per turn, with
supervisor/classify/agent/tool spans nested underneath.

Isolated behind `TurnTracer` so the orchestrator/turn service depends on
this narrow interface, not the Galileo SDK's own shape directly — the SDK's
exact method names are only pinned down for certain during the live
verification step in the approved plan (checking the Galileo dashboard for
a real trace); if that surfaces a mismatch, only this file needs to change.

Every method swallows and logs its own failures rather than raising:
Galileo is observability only, explicitly not part of the TDD gate (see
"Testing discipline" in docs/architecture.md) — a broken or misconfigured
Galileo connection must never take down an actual turn. This includes
construction itself (`TurnTracer.create`), since that's exactly where a bad
credential surfaces.
"""

from __future__ import annotations

import logging

from galileo import GalileoLogger
from galileo_core.schemas.logging.agent import AgentType

logger = logging.getLogger(__name__)


class TurnTracer:
    def __init__(self, logger_: GalileoLogger | None) -> None:
        self._logger = logger_

    @classmethod
    def create(cls, project: str, log_stream: str) -> TurnTracer:
        try:
            return cls(GalileoLogger(project=project, log_stream=log_stream))
        except Exception:
            logger.exception("Galileo tracing unavailable — continuing without it this turn.")
            return cls(None)

    def start_session(self, conversation_id: str) -> None:
        if self._logger is None:
            return
        try:
            self._logger.start_session(name=conversation_id)
        except Exception:
            logger.exception("Galileo start_session failed")

    def start_trace(self, user_message: str, turn_id: str) -> None:
        if self._logger is None:
            return
        try:
            self._logger.start_trace(input=user_message, name=f"turn:{turn_id}")
        except Exception:
            logger.exception("Galileo start_trace failed")

    def conclude_trace(self, output: str, status_code: int = 0) -> None:
        if self._logger is None:
            return
        try:
            self._logger.conclude(output=output, status_code=status_code)
        except Exception:
            logger.exception("Galileo conclude_trace failed")

    def start_span(self, agent_type: AgentType, name: str, input: str) -> None:
        """`agent_type` must be a real `AgentType` member — confirmed live
        that an arbitrary string (e.g. "classify") is silently dropped by
        the SDK with no exception, no error, and no span. See
        tests/test_galileo_tracer.py for the full story."""
        if self._logger is None:
            return
        try:
            self._logger.add_agent_span(input=input, name=name, agent_type=agent_type)
        except Exception:
            logger.exception("Galileo start_span failed")

    def conclude_span(self, output: str, status_code: int = 0) -> None:
        if self._logger is None:
            return
        try:
            self._logger.conclude(output=output, status_code=status_code)
        except Exception:
            logger.exception("Galileo conclude_span failed")

    def flush(self) -> None:
        if self._logger is None:
            return
        try:
            self._logger.flush()
        except Exception:
            logger.exception("Galileo flush failed")
