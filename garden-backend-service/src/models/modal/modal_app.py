from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.modal.modal_function import ModalFunction
    from src.models.user import User

else:
    ModalFunction = "ModalFunction"
    User = "User"


class ModalApp(Base):
    __tablename__ = "modal_apps"
    id: Mapped[int] = mapped_column(primary_key=True)
    app_name: Mapped[str]
    base_image_name: Mapped[str]
    requirements: Mapped[list[str]] = mapped_column(ARRAY(String))

    # The whole Python file the user submitted with the Modal App definition
    file_contents: Mapped[str]

    modal_functions: Mapped[list[ModalFunction]] = relationship(
        ModalFunction,
        back_populates="modal_app",
        lazy="selectin",
        cascade="delete, delete-orphan, save-update, merge",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")
