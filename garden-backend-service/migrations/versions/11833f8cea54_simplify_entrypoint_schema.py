"""simplify entrypoint schema

Revision ID: 11833f8cea54
Revises: fdbefac8521a
Create Date: 2024-07-02 16:11:39.450210

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "11833f8cea54"
down_revision: Union[str, None] = "fdbefac8521a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("model_metadata")
    op.drop_table("dataset_metadata")
    op.drop_table("paper_metadata")
    op.drop_table("repository_metadata")
    op.add_column(
        "entrypoints",
        sa.Column("requirements", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "entrypoints",
        sa.Column(
            "models",
            postgresql.ARRAY(postgresql.JSON(astext_type=sa.Text())),
            nullable=True,
        ),
    )
    op.add_column(
        "entrypoints",
        sa.Column(
            "repositories",
            postgresql.ARRAY(postgresql.JSON(astext_type=sa.Text())),
            nullable=True,
        ),
    )
    op.add_column(
        "entrypoints",
        sa.Column(
            "papers",
            postgresql.ARRAY(postgresql.JSON(astext_type=sa.Text())),
            nullable=True,
        ),
    )
    op.add_column(
        "entrypoints",
        sa.Column(
            "datasets",
            postgresql.ARRAY(postgresql.JSON(astext_type=sa.Text())),
            nullable=True,
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("entrypoints", "datasets")
    op.drop_column("entrypoints", "papers")
    op.drop_column("entrypoints", "repositories")
    op.drop_column("entrypoints", "models")
    op.drop_column("entrypoints", "requirements")
    op.create_table(
        "repository_metadata",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("repo_name", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("url", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("entrypoint_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "contributors",
            postgresql.ARRAY(sa.VARCHAR()),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["entrypoint_id"],
            ["entrypoints.id"],
            name="repository_metadata_entrypoint_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="repository_metadata_pkey"),
    )
    op.create_table(
        "paper_metadata",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("doi", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("citation", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("entrypoint_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("title", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "authors",
            postgresql.ARRAY(sa.VARCHAR()),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["entrypoint_id"],
            ["entrypoints.id"],
            name="paper_metadata_entrypoint_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="paper_metadata_pkey"),
    )
    op.create_table(
        "dataset_metadata",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("doi", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("url", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("data_type", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("repository", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("entrypoint_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("title", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["entrypoint_id"],
            ["entrypoints.id"],
            name="dataset_metadata_entrypoint_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="dataset_metadata_pkey"),
    )
    op.create_table(
        "model_metadata",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "model_identifier", sa.VARCHAR(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "model_repository", sa.VARCHAR(), autoincrement=False, nullable=False
        ),
        sa.Column("model_version", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column("entrypoint_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["entrypoint_id"],
            ["entrypoints.id"],
            name="model_metadata_entrypoint_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="model_metadata_pkey"),
    )
    # ### end Alembic commands ###
