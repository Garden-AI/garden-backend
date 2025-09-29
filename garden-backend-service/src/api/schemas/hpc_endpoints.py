from src.api.schemas.base import BaseSchema


class HpcEndpointBase(BaseSchema):
    name: str
    gcmu_id: str  # Globus Compute endpoint UUID


class HpcEndpointCreateRequest(HpcEndpointBase):
    pass


class HpcEndpointResponse(HpcEndpointBase):
    id: int


class HpcEndpointPatchRequest(BaseSchema):
    name: str | None = None
    gcmu_id: str | None = None
