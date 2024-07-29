from sqlalchemy import Column, ForeignKey, Integer, Table
from src.models.base import Base

gardens_entrypoints = Table(
    "gardens_entrypoints",
    Base.metadata,
    Column("garden_id", ForeignKey("gardens.id"), primary_key=True),
    Column("entrypoint_id", ForeignKey("entrypoints.id"), primary_key=True),
)

users_saved_gardens = Table(
    "users_saved_gardens",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("garden_id", Integer, ForeignKey("gardens.id"), primary_key=True),
)

entrypoints_mdf_datasets = Table(
    "entrypoints_mdf_datasets",
    Base.metadata,
    Column("entrypoint_id", Integer, ForeignKey("entrypoints.id"), primary_key=True),
    Column("dataset_id", Integer, ForeignKey("mdf_datasets.id"), primary_key=True),
)
