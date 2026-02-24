"""add_user_advanced_mode

Revision ID: 561c2fc8094c
Revises: 47858283c702
Create Date: 2026-02-24 20:37:10.068113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '561c2fc8094c'
down_revision: Union[str, Sequence[str], None] = '47858283c702'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('advanced_mode', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'advanced_mode')
