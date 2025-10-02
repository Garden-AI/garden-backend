from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._associations import hpc_functions_hpc_deployments
from src.models.base import Base
from src.models.functions.common import (
    AssociatedMaterialsMixin,
    DoiMixin,
    FunctionMetadataMixin,
)

if TYPE_CHECKING:
    from src.models.user import User

    from .hpc_deployments import HpcDeployment
    from .hpc_endpoints import HpcEndpoint
    from .hpc_invocations import HpcInvocationLog
else:
    User = "User"
    HpcDeployment = "HpcDeployment"
    HpcEndpoint = "HpcEndpoint"
    HpcInvocationLog = "HpcInvocationLog"


class HpcFunction(Base, DoiMixin, AssociatedMaterialsMixin, FunctionMetadataMixin):
    __tablename__ = "hpc_functions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship()

    deployments: Mapped[list["HpcDeployment"]] = relationship(
        secondary=hpc_functions_hpc_deployments,
        lazy="selectin",
        back_populates="functions",
    )

    invocation_logs: Mapped[list["HpcInvocationLog"]] = relationship(
        back_populates="function",
        lazy="selectin",
    )

    @property
    def owner(self) -> "User":
        return self.user

    @property
    def num_invocations(self) -> int:
        return len(self.invocation_logs)

    @property
    def available_endpoints(self) -> list[str]:
        """Return unique list of endpoint IDs across all deployments."""
        endpoint_ids = set()
        for deployment in self.deployments:
            for endpoint in deployment.endpoints:
                endpoint_ids.add(endpoint.gcmu_id)
        return list(endpoint_ids)

    @property
    def available_deployments(self) -> list[dict]:
        """Return deployment info for each (deployment, endpoint) pair."""
        result = []

        for deployment in self.deployments:
            for endpoint in deployment.endpoints:
                result.append(
                    {
                        "deployment_id": deployment.id,
                        "endpoint_name": endpoint.name,
                        "endpoint_gcmu_id": endpoint.gcmu_id,
                        "conda_env_path": deployment.conda_env_path,
                    }
                )

        return result
