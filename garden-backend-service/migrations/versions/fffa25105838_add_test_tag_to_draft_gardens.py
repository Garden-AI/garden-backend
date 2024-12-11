"""add test tag to draft gardens

Revision ID: fffa25105838
Revises: 439848cfb104
Create Date: 2024-12-11 16:52:14.752384

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import column, select, table
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fffa25105838"
down_revision: Union[str, None] = "439848cfb104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a temporary connection
    connection = op.get_bind()

    # Define table structure we need for the query
    gardens = table(
        "gardens",
        column("id", postgresql.INTEGER),
        column("doi_is_draft", postgresql.BOOLEAN),
        column("tags", postgresql.ARRAY(postgresql.VARCHAR)),
    )

    # Find all draft gardens
    draft_gardens = connection.execute(
        select(gardens.c.id, gardens.c.tags).where(gardens.c.doi_is_draft == True)  # noqa: E712
    ).fetchall()

    # Update each draft garden's tags
    for garden_id, current_tags in draft_gardens:
        # Handle case where tags is None
        if current_tags is None:
            new_tags = ["test"]
        else:
            # Only add 'test' if it's not already present
            if "test" not in current_tags:
                new_tags = current_tags + ["test"]
            else:
                continue  # Skip if 'test' is already present

        # Update the garden's tags
        connection.execute(
            gardens.update().where(gardens.c.id == garden_id).values(tags=new_tags)
        )


def downgrade() -> None:
    # Create a temporary connection
    connection = op.get_bind()

    # Define table structure we need for the query
    gardens = table(
        "gardens",
        column("id", postgresql.INTEGER),
        column("doi_is_draft", postgresql.BOOLEAN),
        column("tags", postgresql.ARRAY(postgresql.VARCHAR)),
    )

    # Find all draft gardens
    draft_gardens = connection.execute(
        select(gardens.c.id, gardens.c.tags).where(gardens.c.doi_is_draft == True)  # noqa: E712
    ).fetchall()

    # Remove 'test' tag from each draft garden's tags
    for garden_id, current_tags in draft_gardens:
        if current_tags and "test" in current_tags:
            new_tags = [tag for tag in current_tags if tag != "test"]
            # Update the garden's tags
            connection.execute(
                gardens.update()
                .where(gardens.c.id == garden_id)
                .values(tags=new_tags if new_tags else None)
            )
