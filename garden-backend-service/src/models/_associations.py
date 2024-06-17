from sqlalchemy import Table, Column, ForeignKey
from src.models.base import Base


gardens_entrypoints = Table(
    "gardens_entrypoints",
    Base.metadata,
    Column("garden_id", ForeignKey("gardens.id"), primary_key=True),
    Column("entrypoint_id", ForeignKey("entrypoints.id"), primary_key=True),
)
