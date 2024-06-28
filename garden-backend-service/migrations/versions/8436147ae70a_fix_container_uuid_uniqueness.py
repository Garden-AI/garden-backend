"""fix container_uuid uniqueness

Revision ID: 8436147ae70a
Revises: 4b5beed10eae
Create Date: 2024-06-11 00:32:45.375305

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8436147ae70a"
down_revision: Union[str, None] = "4b5beed10eae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("entrypoints_container_uuid_key", "entrypoints", type_="unique")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(
        "entrypoints_container_uuid_key", "entrypoints", ["container_uuid"]
    )
    # ### end Alembic commands ###
