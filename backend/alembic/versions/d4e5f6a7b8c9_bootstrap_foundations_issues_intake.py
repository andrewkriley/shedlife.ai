"""bootstrap foundations, issues, and intake agent

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-20 00:00:00.000000
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUB_AGENTS_TABLE = sa.table(
    "sub_agents",
    sa.column("id", sa.String),
    sa.column("macro_category", sa.String),
    sa.column("description", sa.String),
    sa.column("system_prompt", sa.String),
    sa.column("tools", postgresql.JSON),
    sa.column("default_provider", sa.String),
    sa.column("default_model", sa.String),
    sa.column("provenance", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
)

INTAKE_PROMPT = """\
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

INTAKE_TOOLS = [
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


def upgrade() -> None:
    op.create_table(
        "foundations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document", postgresql.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "local_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("filed_externally", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.bulk_insert(
        SUB_AGENTS_TABLE,
        [
            {
                "id": "bootstrap.intake",
                "macro_category": "assist",
                "description": "Collect, validate, and probe tenant foundations so Deploy can start",
                "system_prompt": INTAKE_PROMPT,
                "tools": INTAKE_TOOLS,
                "default_provider": "anthropic",
                "default_model": "claude-haiku-4-5",
                "provenance": "declared",
                "created_at": datetime.now(timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    op.execute(SUB_AGENTS_TABLE.delete().where(SUB_AGENTS_TABLE.c.id == "bootstrap.intake"))
    op.drop_table("local_issues")
    op.drop_table("foundations")
