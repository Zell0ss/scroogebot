"""add active_basket_id to users

Revision ID: d4e5f6a7b890
Revises: c3d4e5f6a789
Create Date: 2026-02-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b890'
down_revision = 'c3d4e5f6a789'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('active_basket_id', sa.Integer(), sa.ForeignKey('baskets.id'), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'active_basket_id')
