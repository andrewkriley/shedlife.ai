"""identity provider_user_id required with unique constraint

Revision ID: 7a4126f97080
Revises: 27220548e778
Create Date: 2026-09-19 07:12:41.329680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a4126f97080'
down_revision: Union[str, Sequence[str], None] = '27220548e778'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('identities', 'provider_user_id',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.create_unique_constraint(
        'uq_identities_provider_provider_user_id', 'identities', ['provider', 'provider_user_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_identities_provider_provider_user_id', 'identities', type_='unique')
    op.alter_column('identities', 'provider_user_id',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
