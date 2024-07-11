from uuid import UUID

from pydantic import EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber

from .base import BaseSchema, UniqueList


class UserBase(BaseSchema):
    username: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone_number: PhoneNumber | None = None
    affiliations: UniqueList[str] | None = None
    skills: UniqueList[str] | None = None
    domains: UniqueList[str] | None = None
    profile_pic_id: int | None = None


class UserMetadataResponse(UserBase):
    identity_id: UUID
    saved_garden_dois: UniqueList[str]


class UserUpdateRequest(UserBase):
    pass
