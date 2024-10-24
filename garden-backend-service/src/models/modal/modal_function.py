from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    doi: Mapped[str | None] = mapped_column(unique=True)
    doi_is_draft: Mapped[bool] = mapped_column(default=True)

    title: Mapped[str]
    authors: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String))
    description: Mapped[str | None]
    year: Mapped[str]
    language: Mapped[str] = "en"
    version: Mapped[str] = "0.0.1"
    is_archived: Mapped[bool] = mapped_column(default=False)

    function_name: Mapped[str]
    function_text: Mapped[str]
    hardware_spec: Mapped[dict] = mapped_column(JSON)

    test_functions: Mapped[list[str]] = mapped_column(ARRAY(String))

    # NOTE: modifications to these lists / dictionaries won't be picked up
    # by sqlalchemy ORM. Updates should replace with a copy.
    models: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    repositories: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    papers: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))
    datasets: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON))

    modal_app_id: Mapped[int] = mapped_column(ForeignKey("modal_apps.id"))
    modal_app: Mapped[ModalApp] = relationship(
        ModalApp, back_populates="modal_functions", lazy="selectin"
    )

    @property
    def owner(self) -> User:
        return self.modal_app.owner
