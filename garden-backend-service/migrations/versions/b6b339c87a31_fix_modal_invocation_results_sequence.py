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
    # Create sequence for modal_invocation_results if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'modal_invocation_results_id_seq') THEN
                CREATE SEQUENCE modal_invocation_results_id_seq;
            END IF;
        END $$;
    """)

    # Get the current maximum ID and set the sequence value
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
    # Remove the default value
    op.execute("""
        ALTER TABLE modal_invocation_results
        ALTER COLUMN id DROP DEFAULT
    """)

    # Remove the sequence if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'modal_invocation_results_id_seq') THEN
                DROP SEQUENCE modal_invocation_results_id_seq;
            END IF;
        END $$;
    """)
