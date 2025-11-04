from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from src.models._associations import hpc_functions_hpc_endpoints
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user import User

    from .hpc_functions import HpcFunction
else:
    User = "User"
    HpcFunction = "HpcFunction"


class HpcEndpoint(Base):
    __tablename__ = "hpc_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    gcmu_id: Mapped[str | None]
    functions: Mapped[list["HpcFunction"]] = relationship(
        secondary=hpc_functions_hpc_endpoints,
        back_populates="endpoints",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(lazy="selectin")
    owner: Mapped["User"] = synonym("user")
