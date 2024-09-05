from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from src.models._associations import modal_apps_modal_functions
from src.models.base import Base

if TYPE_CHECKING:
    from src.models.modal.modal_app import ModalApp
    from src.models.user import User

else:
    ModalApp = "ModalApp"
    User = "User"

class ModalFunction(Base):
    __tablename__ = "modal_functions"
    id: Mapped[int] = mapped_column(primary_key=True)
    doi: Mapped[str] = mapped_column(unique=True)
    doi_is_draft: Mapped[bool] = mapped_column(default=True)
    
    authors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    contributors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    description: Mapped[str | None]
    publisher: Mapped[str]
    year: Mapped[str]
    language: Mapped[str]
    version: Mapped[str]
    is_archived: Mapped[bool] = mapped_column(default=False)

    # short_name is name of the function
    short_name: Mapped[str]
    function_text: Mapped[str]

    tags: Mapped[list[str]] = mapped_column(ARRAY(String))
    test_functions: Mapped[list[str]] = mapped_column(ARRAY(String))
    requirements: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # NOTE: modifications to these lists / dictionaries won't be picked up
    # by sqlalchemy ORM. Updates should replace with a copy.
    models: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    repositories: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    papers: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    datasets: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship(lazy="selectin")
    owner: Mapped[User] = synonym("user")

    modal_app: Mapped[ModalApp] = relationship(
        ModalApp,
        secondary=modal_apps_modal_functions,
        back_populates="modal_functions",
        lazy="selectin",
        cascade="save-update, merge, refresh-expire, expunge",
    )