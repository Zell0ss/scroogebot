"""drop unique constraint on baskets.name (allow reuse of soft-deleted names)

Revision ID: e5f6a7b8c901
Revises: d4e5f6a7b890
Create Date: 2026-02-22
"""
from alembic import op

revision = 'e5f6a7b8c901'
down_revision = 'd4e5f6a7b890'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('name', table_name='baskets')


def downgrade() -> None:
    op.create_index('name', 'baskets', ['name'], unique=True)
