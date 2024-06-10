from sqlalchemy import Table, Column, ForeignKey
from src.models.base import Base


gardens_entrypoints = Table(
    "gardens_entrypoints",
    Base.metadata,
    Column("garden_doi", ForeignKey("gardens.doi"), primary_key=True),
    Column("entrypoint_doi", ForeignKey("entrypoints.doi"), primary_key=True),
)
