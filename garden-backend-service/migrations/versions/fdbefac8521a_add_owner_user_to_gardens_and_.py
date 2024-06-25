"""add owner/user to gardens and entrypoints

Revision ID: fdbefac8521a
Revises: b56d8ac560a5
Create Date: 2024-06-18 20:01:12.749566

"""
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fdbefac8521a"
down_revision: Union[str, None] = "b56d8ac560a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # edited alembic commands:

    # add column as nullable first
    op.add_column("entrypoints", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("gardens", sa.Column("user_id", sa.Integer(), nullable=True))

    conn = op.get_bind()
    # ensure users has a row for the default owner (owen :))
    owen_identity_id = UUID("76024960-c68b-4fec-8cb8-b65b096f18da")
    result = conn.execute(
        sa.text("SELECT id FROM users WHERE identity_id = :owen_identity_id"),
        {"owen_identity_id": owen_identity_id},
    )
    owen_user_id = result.scalar()

    # add owen if not present
    if owen_user_id is None:
        conn.execute(
            sa.text(
                "INSERT INTO users (username, identity_id) VALUES (:username, :identity_id)"
            ),
            {
                "username": "owenpriceskelly@uchicago.edu",
                "identity_id": owen_identity_id,
            },
        )
        result = conn.execute(
            sa.text("SELECT id FROM users WHERE identity_id = :owen_identity_id"),
            {"owen_identity_id": owen_identity_id},
        )
        owen_user_id = result.scalar()
        assert owen_user_id is not None

    # make owen default owner
    conn.execute(
        sa.text("UPDATE entrypoints SET user_id = :owen_user_id WHERE user_id IS NULL"),
        {"owen_user_id": owen_user_id},
    )
    conn.execute(
        sa.text("UPDATE gardens SET user_id = :owen_user_id WHERE user_id IS NULL"),
        {"owen_user_id": owen_user_id},
    )
    # Alter columns to be non-nullable
    op.alter_column(
        "entrypoints", "user_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column("gardens", "user_id", existing_type=sa.Integer(), nullable=False)

    # add foreign key constraints
    op.create_foreign_key(None, "entrypoints", "users", ["user_id"], ["id"])
    op.create_foreign_key(None, "gardens", "users", ["user_id"], ["id"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "gardens", type_="foreignkey")
    op.drop_column("gardens", "user_id")
    op.drop_constraint(None, "entrypoints", type_="foreignkey")
    op.drop_column("entrypoints", "user_id")
    # ### end Alembic commands ###
