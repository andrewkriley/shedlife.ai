"""The four Phase 1 playbooks. The model may not add a fifth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    tool: str
    required: bool = True
    has_side_effects: bool = False


@dataclass(frozen=True)
class Playbook:
    id: str
    steps: tuple[Step, ...]
    success_when: str


PLAYBOOKS: dict[str, Playbook] = {
    "collect-foundations": Playbook(
        id="collect-foundations",
        steps=(Step(tool="foundations.write", required=True, has_side_effects=False),),
        success_when="known schema fields written",
    ),
    "validate-foundations": Playbook(
        id="validate-foundations",
        steps=(Step(tool="foundations.validate", required=True, has_side_effects=False),),
        success_when="no field errors",
    ),
    "predeploy-probe": Playbook(
        id="predeploy-probe",
        steps=(
            Step(tool="probe.llm_key", required=True),
            Step(tool="probe.outbound_https", required=True),
            Step(tool="probe.proxmox_api", required=True),
            Step(tool="probe.proxmox_capacity", required=False),
            Step(tool="probe.bridge_exists", required=True),
            Step(tool="probe.storage_pool_exists", required=True),
            Step(tool="probe.ntp_ok", required=True),
            Step(tool="probe.ssh_key_installed", required=True, has_side_effects=True),
            Step(tool="probe.adopted_endpoint", required=False),
            Step(tool="probe.domain_resolves", required=False),
        ),
        success_when="required probes pass; warns allowed",
    ),
    "export-state": Playbook(
        id="export-state",
        steps=(Step(tool="foundations.export", required=True, has_side_effects=False),),
        success_when="yaml bundle written",
    ),
}

PLAYBOOK_IDS = frozenset(PLAYBOOKS)


def get_playbook(playbook_id: str) -> Playbook:
    return PLAYBOOKS[playbook_id]
