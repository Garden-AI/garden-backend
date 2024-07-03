from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models._associations import users_saved_gardens
from src.models.base import Base

if TYPE_CHECKING:
    from src.models import Garden


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[Optional[str]]
    identity_id: Mapped[UUID] = mapped_column(unique=True)
    name: Mapped[Optional[str]]
    email: Mapped[Optional[str]] = mapped_column(unique=True)
    phone_number: Mapped[Optional[str]]
    skills: Mapped[Optional[list[str]]] = mapped_column(postgresql.ARRAY(String))
    domains: Mapped[Optional[list[str]]] = mapped_column(postgresql.ARRAY(String))
    affiliations: Mapped[Optional[list[str]]] = mapped_column(postgresql.ARRAY(String))

    saved_gardens: Mapped[list["Garden"]] = relationship(
        "Garden",
        secondary=users_saved_gardens,
        back_populates="users",
        lazy="selectin",
    )

    @property
    def saved_garden_dois(self):
        return [garden.doi for garden in self.saved_gardens]
