"""Playbook runner, per docs/spec/bootstrap.md.

The agent picks a playbook id and arguments. This engine refuses unknown
ids and runs predetermined steps. No model in here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from theshed.playbooks.catalog import PLAYBOOKS, Playbook, Step


class UnknownPlaybook(ValueError):
    pass


@dataclass
class StepResult:
    tool: str
    status: str
    detail: str = ""


@dataclass
class PlaybookResult:
    playbook_id: str
    ok: bool
    steps: list[StepResult] = field(default_factory=list)


Execute = Callable[[Step], str]


def run_playbook(playbook_id: str, execute: Execute) -> PlaybookResult:
    playbook = PLAYBOOKS.get(playbook_id)
    if playbook is None:
        raise UnknownPlaybook(playbook_id)

    results: list[StepResult] = []
    for step in playbook.steps:
        try:
            detail = execute(step)
            results.append(StepResult(tool=step.tool, status="done", detail=detail))
        except Exception as exc:
            results.append(StepResult(tool=step.tool, status="error", detail=str(exc)))
            if step.required:
                return PlaybookResult(playbook_id=playbook_id, ok=False, steps=results)
    return PlaybookResult(playbook_id=playbook_id, ok=True, steps=results)


def get_playbook(playbook_id: str) -> Playbook:
    playbook = PLAYBOOKS.get(playbook_id)
    if playbook is None:
        raise UnknownPlaybook(playbook_id)
    return playbook
