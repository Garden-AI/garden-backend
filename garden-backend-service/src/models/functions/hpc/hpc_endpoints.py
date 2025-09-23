from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._associations import hpc_deployment_endpoints
from src.models.base import Base

if TYPE_CHECKING:
    from .hpc_deployments import HpcDeployment
else:
    HpcDeployment = "HpcDeployment"


class HpcEndpoint(Base):
    __tablename__ = "hpc_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    gcmu_id: Mapped[str]

    deployments: Mapped[list["HpcDeployment"]] = relationship(
        secondary=hpc_deployment_endpoints,
        back_populates="endpoints",
    )
