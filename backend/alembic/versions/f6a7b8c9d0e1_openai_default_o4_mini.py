"""bootstrap.intake default OpenAI model is o4-mini

Revision ID: f6a7b8c9d0e1
Revises: h8c9d0e1f2a3
Create Date: 2026-09-20 16:18:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE sub_agents SET default_provider = 'openai', default_model = 'o4-mini' "
            "WHERE id = 'bootstrap.intake'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE sub_agents SET default_provider = 'openai', default_model = 'gpt-5.4' "
            "WHERE id = 'bootstrap.intake'"
        )
    )
