"""assist gains the code_execution tool

Revision ID: b2c3d4e5f6a7
Revises: 6fd1a76f89ab
Create Date: 2026-09-19 09:00:00.000000

Adds Anthropic's native, server-executed code_execution tool to `assist`
alongside web_search — same integration shape (no client-side dispatch,
no new credential beyond the Anthropic API key already in use), confirmed
live via a direct API smoke test before writing this migration. See
docs/prd/core-agentic-loop.md, "The three real sub-agents this phase."
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '6fd1a76f89ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUB_AGENTS_TABLE = sa.table(
    "sub_agents",
    sa.column("id", sa.String),
    sa.column("system_prompt", sa.String),
    sa.column("tools", postgresql.JSON),
)

OLD_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search", "has_side_effects": False},
]
NEW_TOOLS = [
    *OLD_TOOLS,
    {"type": "code_execution_20260521", "name": "code_execution", "has_side_effects": False},
]

OLD_SYSTEM_PROMPT = """\
You are The Shed's general assistant. Answer the user's question directly and \
concisely, using web search when you need current or specific information you \
don't already know. Cite what you found when it materially informs your answer."""

NEW_SYSTEM_PROMPT = """\
You are The Shed's general assistant. Answer the user's question directly and \
concisely, using web search when you need current or specific information you \
don't already know, and code execution when a calculation, data transformation, \
or quick script would get a more reliable answer than reasoning it out yourself. \
Cite what you found when it materially informs your answer."""


def upgrade() -> None:
    op.execute(
        SUB_AGENTS_TABLE.update()
        .where(SUB_AGENTS_TABLE.c.id == "assist")
        .values(tools=NEW_TOOLS, system_prompt=NEW_SYSTEM_PROMPT)
    )


def downgrade() -> None:
    op.execute(
        SUB_AGENTS_TABLE.update()
        .where(SUB_AGENTS_TABLE.c.id == "assist")
        .values(tools=OLD_TOOLS, system_prompt=OLD_SYSTEM_PROMPT)
    )
