from sqlalchemy import Column, ForeignKey, Integer, Table
from src.models.base import Base

gardens_entrypoints = Table(
    "gardens_entrypoints",
    Base.metadata,
    Column("garden_id", ForeignKey("gardens.id"), primary_key=True),
    Column("entrypoint_id", ForeignKey("entrypoints.id"), primary_key=True),
)

users_skills = Table(
    "users_skill",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("skill_id", Integer, ForeignKey("skills.id")),
)

users_domains = Table(
    "users_domains",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("domain_id", Integer, ForeignKey("domains.id")),
)

users_affiliations = Table(
    "users_affiliations",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("affiliation_id", Integer, ForeignKey("affiliations.id")),
)

users_saved_gardens = Table(
    "users_saved_gardens",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("garden_id", Integer, ForeignKey("gardens.id")),
)
