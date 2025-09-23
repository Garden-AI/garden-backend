from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Sequence, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from src.modal.status import AsyncModalJobStatus
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.functions.modal.modal_function import ModalFunction
    from src.models.user import User

else:
    ModalFunction = "ModalFunction"
    User = "User"


class ModalApp(Base):
    __tablename__ = "modal_apps"
    id: Mapped[int] = mapped_column(primary_key=True)
    app_name: Mapped[str]
    original_app_name: Mapped[str]
    base_image_name: Mapped[str]
    requirements: Mapped[list[str]] = mapped_column(ARRAY(String))
    conda_requirements: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    deploy_status: Mapped[AsyncModalJobStatus] = mapped_column(
        default=AsyncModalJobStatus.PENDING
    )
    deploy_error: Mapped[str | None] = mapped_column(nullable=True, default=None)
    suggested_fix: Mapped[str | None] = mapped_column(nullable=True, default=None)
    deployment_output: Mapped[str | None] = mapped_column(nullable=True, default=None)
    modal_app_id: Mapped[str | None] = mapped_column(nullable=True)

    # The whole Python file the user submitted with the Modal App definition
    file_contents: Mapped[str]

    modal_functions: Mapped[list[ModalFunction]] = relationship(
        ModalFunction,
        back_populates="modal_app",
        lazy="selectin",
        cascade="delete, delete-orphan, save-update, merge",
    )

    version: Mapped[int] = mapped_column(
        Sequence("version_sequence", start=1),
        server_default=text("nextval('version_sequence')"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")

    marked_for_deletion: Mapped[datetime | None] = mapped_column(default=None)
