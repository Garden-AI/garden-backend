from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.functions.hpc.hpc_endpoints import HpcEndpoint
    from src.models.functions.hpc.hpc_functions import HpcFunction
    from src.models.user import User
else:
    User = "User"
    HpcFunction = "HpcFunction"
    HpcEndpoint = "HpcEndpoint"


class HpcInvocationLog(Base):
    __tablename__ = "hpc_invocation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship()
    function_id: Mapped[int] = mapped_column(ForeignKey("hpc_functions.id"))
    function: Mapped["HpcFunction"] = relationship(back_populates="invocation_logs")
    hpc_endpoint_id: Mapped[int] = mapped_column(ForeignKey("hpc_endpoints.id"))
    hpc_endpoint: Mapped["HpcEndpoint"] = relationship()
    globus_task_id: Mapped[str]
    date_invoked: Mapped[datetime]
