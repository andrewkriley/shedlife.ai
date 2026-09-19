import pytest

from theshed.playbooks.catalog import PLAYBOOK_IDS, Step, get_playbook
from theshed.playbooks.engine import UnknownPlaybook, run_playbook


def test_catalog_is_exactly_the_four_phase1_playbooks() -> None:
    assert PLAYBOOK_IDS == {
        "collect-foundations",
        "validate-foundations",
        "predeploy-probe",
        "export-state",
    }


def test_unknown_playbook_is_refused() -> None:
    with pytest.raises(UnknownPlaybook):
        run_playbook("invent-topology", execute=lambda _step: "ok")


def test_runs_steps_in_order_and_records_status() -> None:
    seen: list[str] = []

    def execute(step: Step) -> str:
        seen.append(step.tool)
        return "ok"

    result = run_playbook("export-state", execute=execute)
    assert result.ok is True
    assert seen == [step.tool for step in get_playbook("export-state").steps]
    assert all(s.status == "done" for s in result.steps)


def test_required_step_failure_stops_the_playbook() -> None:
    def execute(step: Step) -> str:
        if step.tool == "foundations.validate":
            raise RuntimeError("boom")
        return "ok"

    result = run_playbook("validate-foundations", execute=execute)
    assert result.ok is False
    assert result.steps[0].status == "error"
