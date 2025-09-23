from sqlalchemy import Column, ForeignKey, Integer, PrimaryKeyConstraint, Table

from src.models.base import Base

gardens_entrypoints = Table(
    "gardens_entrypoints",
    Base.metadata,
    Column("garden_id", ForeignKey("gardens.id"), primary_key=True),
    Column("entrypoint_id", ForeignKey("entrypoints.id"), primary_key=True),
)

gardens_modal_functions = Table(
    "gardens_modal_functions",
    Base.metadata,
    Column("garden_id", ForeignKey("gardens.id"), primary_key=True),
    Column(
        "modal_function_id",
        ForeignKey("modal_functions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

gardens_hpc_functions = Table(
    "gardens_hpc_functions",
    Base.metadata,
    Column("garden_id", ForeignKey("gardens.id"), primary_key=True),
    Column(
        "hpc_function_id",
        ForeignKey("hpc_functions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

users_saved_gardens = Table(
    "users_saved_gardens",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("garden_id", Integer, ForeignKey("gardens.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("user_id", "garden_id"),
)

entrypoints_mdf_datasets = Table(
    "entrypoints_mdf_datasets",
    Base.metadata,
    Column("entrypoint_id", Integer, ForeignKey("entrypoints.id"), primary_key=True),
    Column("dataset_id", Integer, ForeignKey("mdf_datasets.id"), primary_key=True),
)

hpc_deployment_endpoints = Table(
    "hpc_deployment_endpoints",
    Base.metadata,
    Column(
        "hpc_deployment_id", Integer, ForeignKey("hpc_deployments.id"), primary_key=True
    ),
    Column(
        "hpc_endpoint_id", Integer, ForeignKey("hpc_endpoints.id"), primary_key=True
    ),
)
