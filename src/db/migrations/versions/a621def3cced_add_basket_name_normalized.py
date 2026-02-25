"""add_basket_name_normalized

Revision ID: a621def3cced
Revises: 561c2fc8094c
Create Date: 2026-02-25 21:10:38.797320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a621def3cced'
down_revision: Union[str, Sequence[str], None] = '561c2fc8094c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import unicodedata

    def _norm(s: str) -> str:
        nfkd = unicodedata.normalize('NFKD', s.strip())
        stripped = ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()
        return ' '.join(stripped.split())

    # Step 1: add as nullable
    op.add_column('baskets', sa.Column('name_normalized', sa.String(100), nullable=True))

    # Step 2: populate existing rows using Python unicodedata
    conn = op.get_bind()
    for row in conn.execute(sa.text("SELECT id, name FROM baskets")):
        conn.execute(
            sa.text("UPDATE baskets SET name_normalized = :n WHERE id = :id"),
            {"n": _norm(row.name), "id": row.id},
        )

    # Step 3: apply NOT NULL + UNIQUE
    op.alter_column('baskets', 'name_normalized', existing_type=sa.String(100), nullable=False)
    op.create_unique_constraint('uq_baskets_name_normalized', 'baskets', ['name_normalized'])


def downgrade() -> None:
    op.drop_constraint('uq_baskets_name_normalized', 'baskets', type_='unique')
    op.drop_column('baskets', 'name_normalized')
