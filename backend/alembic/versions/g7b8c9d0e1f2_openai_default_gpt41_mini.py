"""bootstrap.intake default OpenAI model is gpt-4.1-mini

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-20 16:31:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE sub_agents SET default_provider = 'openai', "
            "default_model = 'gpt-4.1-mini' "
            "WHERE id = 'bootstrap.intake'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE sub_agents SET default_provider = 'openai', default_model = 'o4-mini' "
            "WHERE id = 'bootstrap.intake'"
        )
    )
