from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._associations import hpc_functions_hpc_endpoints
from src.models.base import Base
from src.models.functions.common import (
    AssociatedMaterialsMixin,
    DoiMixin,
    FunctionMetadataMixin,
)

if TYPE_CHECKING:
    from src.models.user import User

    from .hpc_endpoints import HpcEndpoint
    from .hpc_invocations import HpcInvocationLog
else:
    User = "User"
    HpcEndpoint = "HpcEndpoint"
    HpcInvocationLog = "HpcInvocationLog"


class HpcFunction(Base, DoiMixin, AssociatedMaterialsMixin, FunctionMetadataMixin):
    __tablename__ = "hpc_functions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship()

    endpoints: Mapped[list["HpcEndpoint"]] = relationship(
        secondary=hpc_functions_hpc_endpoints,
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
    def available_endpoints(self) -> list[dict]:
        """Return list of available endpoints with name and ID."""
        return [
            {
                "name": endpoint.name,
                "gcmu_id": endpoint.gcmu_id,
            }
            for endpoint in self.endpoints
        ]
