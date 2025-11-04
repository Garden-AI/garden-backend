from uuid import UUID

from pydantic import AliasPath, Field

from src.api.schemas.base import BaseSchema


class HpcEndpointBase(BaseSchema):
    name: str
    gcmu_id: str | None = None  # Globus Compute endpoint UUID


class HpcEndpointCreateRequest(HpcEndpointBase):
    pass


class HpcEndpointResponse(HpcEndpointBase):
    id: int
    owner: str | None = Field(default=None, validation_alias=AliasPath("owner", "name"))
    owner_identity_id: UUID | None = Field(
        default=None, validation_alias=AliasPath("owner", "identity_id")
    )


class HpcEndpointPatchRequest(BaseSchema):
    name: str | None = None
    gcmu_id: str | None = None
