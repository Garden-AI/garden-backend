"""make sure garden-user relation has a joint pk

Revision ID: bed2401f656e
Revises: 4d528e79513e
Create Date: 2025-03-20 21:27:41.183331

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bed2401f656e"
down_revision: Union[str, None] = "4d528e79513e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing primary key constraint
    op.drop_constraint(
        "users_saved_gardens_pkey", "users_saved_gardens", type_="primary"
    )
    # Create a new composite primary key
    op.create_primary_key(
        "users_saved_gardens_pkey", "users_saved_gardens", ["user_id", "garden_id"]
    )


def downgrade() -> None:
    # Drop the composite primary key
    op.drop_constraint(
        "users_saved_gardens_pkey", "users_saved_gardens", type_="primary"
    )
    # Recreate the original primary key on garden_id only
    op.create_primary_key(
        "users_saved_gardens_pkey", "users_saved_gardens", ["garden_id"]
    )
