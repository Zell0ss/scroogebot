"""add command_logs table

Revision ID: b1c2d3e4f567
Revises: 2df3a1ef5417
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f567'
down_revision: Union[str, Sequence[str], None] = '2df3a1ef5417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'command_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tg_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('command', sa.String(length=50), nullable=False),
        sa.Column('args', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_command_logs_tg_id', 'command_logs', ['tg_id'])
    op.create_index('ix_command_logs_command', 'command_logs', ['command'])


def downgrade() -> None:
    op.drop_index('ix_command_logs_command', 'command_logs')
    op.drop_index('ix_command_logs_tg_id', 'command_logs')
    op.drop_table('command_logs')
