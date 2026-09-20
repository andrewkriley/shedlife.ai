"""bootstrap.intake gains read-only discovery tools

Revision ID: h8c9d0e1f2a3
Revises: e5f6a7b8c9d0
Create Date: 2026-09-20 07:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "h8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUB_AGENTS_TABLE = sa.table(
    "sub_agents",
    sa.column("id", sa.String),
    sa.column("system_prompt", sa.String),
    sa.column("tools", postgresql.JSON),
)

OLD_PROMPT = """\
You are The Shed's bootstrap assistant. Your only job is to collect, validate, \
and probe the tenant foundations so Deploy can start. You fill a predetermined \
schema — you do not invent fields, playbooks, or topology.

Playbooks you may run: collect-foundations, validate-foundations, \
predeploy-probe, export-state. Nothing else.

Use foundations_write for known schema keys, foundations_read to see current \
state, foundations_validate to check it, run_probe for a named probe, and \
export_state for the YAML bundle. Ask the operator for values; do not guess \
secrets. Never echo API keys, root passwords, or SSH private keys.
"""

NEW_PROMPT = """\
You are The Shed's bootstrap assistant. Your only job is to collect, validate, \
and probe the tenant foundations so Deploy can start. You fill a predetermined \
schema — you do not invent fields, playbooks, or topology.

Playbooks you may run: collect-foundations, validate-foundations, \
predeploy-probe, export-state. Nothing else. Discovery tools are not a fifth \
playbook.

During collect-foundations you may enumerate the host and adopted endpoints \
with list_proxmox_nodes, list_bridges, list_storage_pools, proxmox_version, \
discover_gitlab, discover_infisical, discover_dns, and discover_k3s. Those \
tools are read-only and never write the schema. After they return known keys, \
offer them to the operator and write only with foundations_write. Host lists \
skip when Proxmox facts are unavailable. Adopted-platform discovery skips \
unless intent is adopt or brownfield; k3s skips when only kubeconfig_ref is \
set. Do not provision GitLab, Infisical, DNS, or k3s.

Use foundations_write for known schema keys, foundations_read to see current \
state, foundations_validate to check it, run_probe for a named probe, and \
export_state for the YAML bundle. Ask the operator for values; do not guess \
secrets. Never echo API keys, root passwords, or SSH private keys.
"""

OLD_TOOLS = [
    {
        "name": "foundations_write",
        "description": "Merge known foundations fields into the schema store.",
        "input_schema": {
            "type": "object",
            "properties": {"patch": {"type": "object"}},
            "required": ["patch"],
        },
        "has_side_effects": False,
    },
    {
        "name": "foundations_read",
        "description": "Return the current foundations document.",
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "foundations_validate",
        "description": "Validate the foundations schema. Field errors are not issues.",
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "run_probe",
        "description": "Run one predetermined pre-deploy probe by id.",
        "input_schema": {
            "type": "object",
            "properties": {"probe_id": {"type": "string"}},
            "required": ["probe_id"],
        },
        "has_side_effects": False,
    },
    {
        "name": "install_ssh_key",
        "description": "Install the dedicated SSH key on the Proxmox host. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {"root_password": {"type": "string"}},
            "required": ["root_password"],
        },
        "has_side_effects": True,
    },
    {
        "name": "export_state",
        "description": "Export the foundations YAML bundle (secret references only).",
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
]

DISCOVERY_TOOLS = [
    {
        "name": "list_proxmox_nodes",
        "description": (
            "List Proxmox node names from injected host facts. "
            "Read-only; does not write foundations. Skips if facts are unavailable."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "list_bridges",
        "description": (
            "List Linux bridges on the Proxmox host from injected facts. "
            "Read-only; does not write foundations. Skips if facts are unavailable."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "list_storage_pools",
        "description": (
            "List storage pool names from injected Proxmox facts. "
            "Read-only; does not write foundations. Skips if facts are unavailable."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "proxmox_version",
        "description": (
            "Return the Proxmox VE version from injected host facts. "
            "Read-only; does not write foundations. Skips if facts are unavailable."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "discover_gitlab",
        "description": (
            "Shallow reachability check of intent.gitlab.url when mode is adopt. "
            "Returns status and http_status only — never a response body. "
            "Does not write foundations or provision GitLab."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "discover_infisical",
        "description": (
            "Shallow reachability check of intent.infisical.url when mode is adopt. "
            "Returns status and http_status only — never a response body. "
            "Does not write foundations or provision Infisical."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "discover_dns",
        "description": (
            "Shallow reachability check of intent.dns.url when mode is brownfield. "
            "Returns status and http_status only — never a response body. "
            "Does not write foundations or provision DNS."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
    {
        "name": "discover_k3s",
        "description": (
            "Shallow reachability check of intent.k3s.url when mode is adopt. "
            "Skips when only kubeconfig_ref is set. Never returns a response body. "
            "Does not write foundations or provision k3s."
        ),
        "input_schema": {"type": "object", "properties": {}},
        "has_side_effects": False,
    },
]

NEW_TOOLS = [*OLD_TOOLS, *DISCOVERY_TOOLS]


def upgrade() -> None:
    op.execute(
        SUB_AGENTS_TABLE.update()
        .where(SUB_AGENTS_TABLE.c.id == "bootstrap.intake")
        .values(tools=NEW_TOOLS, system_prompt=NEW_PROMPT)
    )


def downgrade() -> None:
    op.execute(
        SUB_AGENTS_TABLE.update()
        .where(SUB_AGENTS_TABLE.c.id == "bootstrap.intake")
        .values(tools=OLD_TOOLS, system_prompt=OLD_PROMPT)
    )
