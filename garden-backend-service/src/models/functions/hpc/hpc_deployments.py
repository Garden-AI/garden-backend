from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._associations import (
    hpc_deployment_endpoints,
    hpc_functions_hpc_deployments,
)
from src.models.base import Base

if TYPE_CHECKING:
    from .hpc_endpoints import HpcEndpoint
    from .hpc_functions import HpcFunction
else:
    HpcFunction = "HpcFunction"
    HpcEndpoint = "HpcEndpoint"


class HpcDeployment(Base):
    __tablename__ = "hpc_deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    conda_env_path: Mapped[str | None]
    user_endpoint_config: Mapped[dict | None] = mapped_column(JSON)
    functions: Mapped[list["HpcFunction"]] = relationship(
        secondary=hpc_functions_hpc_deployments,
        back_populates="deployments",
    )
    endpoints: Mapped[list["HpcEndpoint"]] = relationship(
        secondary=hpc_deployment_endpoints,
        lazy="selectin",
        back_populates="deployments",
    )
