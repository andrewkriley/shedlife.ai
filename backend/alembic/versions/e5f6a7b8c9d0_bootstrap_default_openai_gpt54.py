"""bootstrap.intake default model is openai gpt-5.4

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-20 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE sub_agents SET default_provider = 'openai', default_model = 'gpt-5.4' "
            "WHERE id = 'bootstrap.intake'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE sub_agents SET default_provider = 'anthropic', "
            "default_model = 'claude-haiku-4-5' "
            "WHERE id = 'bootstrap.intake'"
        )
    )
