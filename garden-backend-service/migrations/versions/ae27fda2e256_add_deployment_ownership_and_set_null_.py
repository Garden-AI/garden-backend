"""add_deployment_ownership_and_set_null_on_invocations

Revision ID: ae27fda2e256
Revises: adc39d998ba3
Create Date: 2025-10-14 16:53:13.148923

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ae27fda2e256"
down_revision: Union[str, None] = "adc39d998ba3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id column to hpc_deployments
    op.add_column("hpc_deployments", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "hpc_deployments_user_id_fkey", "hpc_deployments", "users", ["user_id"], ["id"]
    )

    # Drop existing function_id FK constraint
    op.drop_constraint(
        "hpc_invocation_logs_function_id_fkey",
        "hpc_invocation_logs",
        type_="foreignkey",
    )

    # Drop existing hpc_endpoint_id FK constraint
    op.drop_constraint(
        "hpc_invocation_logs_hpc_endpoint_id_fkey",
        "hpc_invocation_logs",
        type_="foreignkey",
    )

    # Make function_id nullable
    op.alter_column(
        "hpc_invocation_logs", "function_id", existing_type=sa.Integer(), nullable=True
    )

    # Make hpc_endpoint_id nullable
    op.alter_column(
        "hpc_invocation_logs",
        "hpc_endpoint_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Recreate function_id FK with SET NULL on delete
    op.create_foreign_key(
        "hpc_invocation_logs_function_id_fkey",
        "hpc_invocation_logs",
        "hpc_functions",
        ["function_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Recreate hpc_endpoint_id FK with SET NULL on delete
    op.create_foreign_key(
        "hpc_invocation_logs_hpc_endpoint_id_fkey",
        "hpc_invocation_logs",
        "hpc_endpoints",
        ["hpc_endpoint_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Revert hpc_invocation_logs FK changes

    # Drop SET NULL FK constraints
    op.drop_constraint(
        "hpc_invocation_logs_function_id_fkey",
        "hpc_invocation_logs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "hpc_invocation_logs_hpc_endpoint_id_fkey",
        "hpc_invocation_logs",
        type_="foreignkey",
    )

    # Make columns NOT NULL again
    op.alter_column(
        "hpc_invocation_logs", "function_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "hpc_invocation_logs",
        "hpc_endpoint_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Recreate FK constraints without ondelete behavior
    op.create_foreign_key(
        "hpc_invocation_logs_function_id_fkey",
        "hpc_invocation_logs",
        "hpc_functions",
        ["function_id"],
        ["id"],
    )
    op.create_foreign_key(
        "hpc_invocation_logs_hpc_endpoint_id_fkey",
        "hpc_invocation_logs",
        "hpc_endpoints",
        ["hpc_endpoint_id"],
        ["id"],
    )

    # Remove user_id from hpc_deployments
    op.drop_constraint(
        "hpc_deployments_user_id_fkey", "hpc_deployments", type_="foreignkey"
    )
    op.drop_column("hpc_deployments", "user_id")
