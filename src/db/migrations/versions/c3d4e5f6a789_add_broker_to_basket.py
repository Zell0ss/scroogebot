"""add broker to basket

Revision ID: c3d4e5f6a789
Revises: b1c2d3e4f567
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a789'
down_revision = 'b1c2d3e4f567'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'baskets',
        sa.Column('broker', sa.String(50), nullable=False, server_default='paper')
    )


def downgrade() -> None:
    op.drop_column('baskets', 'broker')
