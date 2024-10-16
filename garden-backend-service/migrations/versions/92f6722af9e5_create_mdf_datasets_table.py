"""create mdf datasets table

Revision ID: 92f6722af9e5
Revises: f293268b31c5
Create Date: 2024-07-25 16:43:06.732761

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "92f6722af9e5"
down_revision: Union[str, None] = "f293268b31c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "mdf_datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doi", sa.String(), nullable=False),
        sa.Column("versioned_source_id", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("flow_action_id", sa.Uuid(), nullable=False),
        sa.Column("previous_versions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doi"),
        sa.UniqueConstraint("flow_action_id"),
        sa.UniqueConstraint("versioned_source_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("mdf_datasets")
    # ### end Alembic commands ###
