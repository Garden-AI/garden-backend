"""fix modal_invocation_logs sequence

Revision ID: fix_modal_invocation_logs_sequence
Revises: d5ae091961f1
Create Date: 2024-04-15 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_modal_invocation_logs_sequence"
down_revision: Union[str, None] = "d5ae091961f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sequence if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'modal_invocation_logs_id_seq') THEN
                CREATE SEQUENCE modal_invocation_logs_id_seq;
            END IF;
        END $$;
    """)

    # Set the sequence to the max id + 1
    op.execute("""
        SELECT setval('modal_invocation_logs_id_seq', COALESCE((SELECT MAX(id) FROM modal_invocation_logs), 0) + 1, false);
    """)

    # Set the sequence as the default value for the id column
    op.execute("""
        ALTER TABLE modal_invocation_logs
        ALTER COLUMN id SET DEFAULT nextval('modal_invocation_logs_id_seq');
    """)


def downgrade() -> None:
    # Remove the default value from the id column
    op.execute("""
        ALTER TABLE modal_invocation_logs
        ALTER COLUMN id DROP DEFAULT;
    """)

    # Drop the sequence
    op.execute("DROP SEQUENCE IF EXISTS modal_invocation_logs_id_seq")
