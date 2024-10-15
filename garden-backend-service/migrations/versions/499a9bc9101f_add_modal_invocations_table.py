"""add modal_invocations table

Revision ID: 499a9bc9101f
Revises: 84833e6b7062
Create Date: 2024-10-15 13:59:13.145420

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "499a9bc9101f"
down_revision: Union[str, None] = "84833e6b7062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "modal_invocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("function_id", sa.Integer(), nullable=False),
        sa.Column(
            "time_invoked",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("execution_time_seconds", sa.Float(), nullable=False),
        sa.Column("estimated_usage", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["function_id"],
            ["modal_functions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("modal_invocations")
    # ### end Alembic commands ###
