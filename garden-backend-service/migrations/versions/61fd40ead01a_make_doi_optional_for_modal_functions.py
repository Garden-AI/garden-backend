"""make doi optional for Modal functions

Revision ID: 61fd40ead01a
Revises: 90d3af5c19d3
Create Date: 2024-09-30 22:35:14.112597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61fd40ead01a'
down_revision: Union[str, None] = '90d3af5c19d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('modal_functions', 'doi',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('modal_functions', 'doi',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###
