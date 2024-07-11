from typing import TYPE_CHECKING
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
    username: Mapped[str | None]
    identity_id: Mapped[UUID] = mapped_column(unique=True)
    name: Mapped[str | None]
    email: Mapped[str | None]
    phone_number: Mapped[str | None]
    skills: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    domains: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    affiliations: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))

    saved_gardens: Mapped[list["Garden"]] = relationship(
        "Garden",
        secondary=users_saved_gardens,
        lazy="select",
    )
