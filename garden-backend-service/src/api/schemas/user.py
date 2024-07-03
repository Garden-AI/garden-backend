from uuid import UUID

from pydantic import BaseModel, EmailStr

from .base import UniqueList


class UserBase(BaseModel):
    username: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    affiliations: UniqueList[str] | None = None
    skills: UniqueList[str] | None = None
    domains: UniqueList[str] | None = None


class UserMetadataResponse(UserBase):
    identity_id: UUID
    saved_garden_dois: UniqueList[str]


class UserUpdateRequest(UserBase):
    pass
