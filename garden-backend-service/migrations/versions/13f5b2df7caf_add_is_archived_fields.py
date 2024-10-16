"""add is_archived fields

Revision ID: 13f5b2df7caf
Revises: 3a7478813c63
Create Date: 2024-08-01 15:40:16.361721

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13f5b2df7caf"
down_revision: Union[str, None] = "3a7478813c63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "entrypoints",
        sa.Column(
            "is_archived", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "gardens",
        sa.Column(
            "is_archived", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("gardens", "is_archived")
    op.drop_column("entrypoints", "is_archived")
    # ### end Alembic commands ###
