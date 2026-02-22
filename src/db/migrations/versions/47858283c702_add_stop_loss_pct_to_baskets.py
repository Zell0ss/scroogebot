"""add_stop_loss_pct_to_baskets

Revision ID: 47858283c702
Revises: e5f6a7b8c901
Create Date: 2026-02-22 22:37:13.876440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '47858283c702'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('baskets', sa.Column('stop_loss_pct', sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('baskets', 'stop_loss_pct')
