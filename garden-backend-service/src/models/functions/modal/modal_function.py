from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.functions.common import (
    AssociatedMaterialsMixin,
    DoiMixin,
    FunctionMetadataMixin,
)

if TYPE_CHECKING:
    from src.models.functions.modal.invocations import ModalInvocationLog
    from src.models.functions.modal.modal_app import ModalApp
    from src.models.user import User

else:
    ModalApp = "ModalApp"
    User = "User"


class ModalFunction(Base, DoiMixin, AssociatedMaterialsMixin, FunctionMetadataMixin):
    __tablename__ = "modal_functions"
    id: Mapped[int] = mapped_column(primary_key=True)
    hardware_spec: Mapped[dict] = mapped_column(JSON)

    modal_app_id: Mapped[int] = mapped_column(ForeignKey("modal_apps.id"))
    modal_app: Mapped[ModalApp] = relationship(
        ModalApp, back_populates="modal_functions", lazy="selectin"
    )

    invocation_logs: Mapped[list["ModalInvocationLog"]] = relationship(
        "ModalInvocationLog",
        back_populates="function",
        lazy="selectin",
    )

    @property
    def num_invocations(self) -> int:
        return len(self.invocation_logs)

    @property
    def owner(self) -> User:
        return self.modal_app.owner

    @property
    def file_contents(self) -> str:
        return self.modal_app.file_contents
