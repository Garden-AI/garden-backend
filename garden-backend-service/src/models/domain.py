from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base
from src.models.user import User


class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    users: Mapped[list[User]] = relationship(
        "User", secondary="users_domains", back_populates="domains"
    )
