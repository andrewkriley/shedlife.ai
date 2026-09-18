"""Galileo tracing, per docs/architecture.md and docs/spec/core-agentic-loop.md:
one Galileo session per conversation, one trace per turn, with
supervisor/classify/agent/tool spans nested underneath.

Isolated behind `TurnTracer` so the orchestrator/turn service depends on
this narrow interface, not the Galileo SDK's own shape directly — the SDK's
exact method names are only pinned down for certain during the live
verification step in the approved plan (checking the Galileo dashboard for
a real trace); if that surfaces a mismatch, only this file needs to change.
"""

from __future__ import annotations

from galileo import GalileoLogger


class TurnTracer:
    def __init__(self, project: str, log_stream: str) -> None:
        self._logger = GalileoLogger(project=project, log_stream=log_stream)

    def start_session(self, conversation_id: str) -> None:
        self._logger.start_session(name=conversation_id)

    def start_trace(self, user_message: str, turn_id: str) -> None:
        self._logger.start_trace(input=user_message, name=f"turn:{turn_id}")

    def conclude_trace(self, output: str, status_code: int = 0) -> None:
        self._logger.conclude(output=output, status_code=status_code)

    def start_span(self, agent_type: str, name: str, input: str) -> None:
        self._logger.add_agent_span(input=input, name=name, agent_type=agent_type)

    def conclude_span(self, output: str, status_code: int = 0) -> None:
        self._logger.conclude(output=output, status_code=status_code)

    def flush(self) -> None:
        self._logger.flush()
