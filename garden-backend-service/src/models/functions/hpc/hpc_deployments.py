from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._associations import hpc_deployment_endpoints
from src.models.base import Base

if TYPE_CHECKING:
    from .hpc_endpoints import HpcEndpoint
    from .hpc_functions import HpcFunction
else:
    HpcFunction = "HpcFunction"
    HpcEndpoint = "HpcEndpoint"


class DeploymentType(str, Enum):
    CONDA = "conda"
    UV = "uv"


class HpcDeployment(Base):
    __tablename__ = "hpc_deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    deployment_type: Mapped[DeploymentType] = mapped_column(String(10))

    conda_env_name: Mapped[str | None]
    conda_env_path: Mapped[str | None]
    conda_requirements: Mapped[JSON | None] = mapped_column(JSON)
    python_dependencies: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    functions: Mapped[list["HpcFunction"]] = relationship(back_populates="deployment")
    endpoints: Mapped[list["HpcEndpoint"]] = relationship(
        secondary=hpc_deployment_endpoints,
        lazy="selectin",
        back_populates="deployments",
    )
