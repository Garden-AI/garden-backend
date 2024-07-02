from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models._associations import (
    users_affiliations,
    users_domains,
    users_saved_gardens,
    users_skills,
)
from src.models.base import Base

if TYPE_CHECKING:
    from src.models import Affiliation, Domain, Garden, Skill


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    identity_id: Mapped[UUID] = mapped_column(unique=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    phone_number: Mapped[str]

    # Relationships
    skills: Mapped[list["Skill"]] = relationship(
        "Skill", secondary=users_skills, back_populates="users"
    )
    domains: Mapped[list["Domain"]] = relationship(
        "Domain", secondary=users_domains, back_populates="users"
    )
    affiliations: Mapped[list["Affiliation"]] = relationship(
        "Affiliation", secondary=users_affiliations, back_populates="users"
    )
    saved_gardens: Mapped[list["Garden"]] = relationship(
        "Garden", secondary=users_saved_gardens, back_populates="users"
    )
