"""seed assist sub-agent

Revision ID: a1b2c3d4e5f6
Revises: 90e19b745088
Create Date: 2026-09-19 07:30:00.000000

The one real, working sub-agent for this slice (docs/prd/core-agentic-loop.md,
"The three real sub-agents this phase" — only `assist` is built in slice 1,
per the approved plan). Uses Anthropic's native, server-executed web_search
tool — no MCP server, no second credential beyond the Anthropic API key
already needed for the LLM call itself.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '90e19b745088'
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

ASSIST_SYSTEM_PROMPT = """\
You are The Shed's general assistant. Answer the user's question directly and \
concisely, using web search when you need current or specific information you \
don't already know. Cite what you found when it materially informs your answer."""


def upgrade() -> None:
    op.bulk_insert(
        SUB_AGENTS_TABLE,
        [
            {
                "id": "assist",
                "macro_category": "assist",
                "description": "General web search/fetch Q&A for everyday questions.",
                "system_prompt": ASSIST_SYSTEM_PROMPT,
                "tools": [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "has_side_effects": False,
                    }
                ],
                "default_provider": "anthropic",
                "default_model": "claude-haiku-4-5",
                "provenance": "manual",
                "created_at": datetime.now(timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    op.execute(SUB_AGENTS_TABLE.delete().where(SUB_AGENTS_TABLE.c.id == "assist"))
