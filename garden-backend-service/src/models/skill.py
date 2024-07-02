from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base

if TYPE_CHECKING:
    from src.models import User


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    users: Mapped[list["User"]] = relationship(
        "User", secondary="users_skills", back_populates="skills"
    )
