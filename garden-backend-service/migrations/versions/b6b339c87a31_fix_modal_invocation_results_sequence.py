"""fix modal_invocation_results sequence

Revision ID: fix_modal_invocation_results_sequence
Revises: b5b389c87931
Create Date: 2024-03-19 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6b339c87a31"
down_revision: Union[str, None] = "b5b389c87931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sequence for modal_invocation_results
    op.execute("CREATE SEQUENCE modal_invocation_results_id_seq")

    # Get the current maximum ID
    op.execute("""
        SELECT setval('modal_invocation_results_id_seq',
            COALESCE((SELECT MAX(id) FROM modal_invocation_results), 0) + 1,
            false)
    """)

    # Update the table to use the sequence
    op.execute("""
        ALTER TABLE modal_invocation_results
        ALTER COLUMN id SET DEFAULT nextval('modal_invocation_results_id_seq')
    """)


def downgrade() -> None:
    # Remove the sequence
    op.execute("DROP SEQUENCE modal_invocation_results_id_seq")

    # Remove the default value
    op.execute("""
        ALTER TABLE modal_invocation_results
        ALTER COLUMN id DROP DEFAULT
    """)
