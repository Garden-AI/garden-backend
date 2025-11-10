from pydantic import Field

from src.api.schemas.base import BaseSchema
from src.api.schemas.shared_function_schemas import (
    CommonFunctionMetadata,
    CommonFunctionMetadataSearchResult,
    CommonFunctionPatchRequest,
)


class HpcFunctionCreateRequest(CommonFunctionMetadata):
    function_name: str
    endpoint_ids: list[int]


class HpcEndpointInfo(BaseSchema):
    name: str
    gcmu_id: str | None


class HpcFunctionSearchResult(CommonFunctionMetadataSearchResult):
    id: int
    function_name: str
    available_endpoints: list[HpcEndpointInfo] = Field(default_factory=list)
    num_invocations: int = 0


class HpcFunctionMetadataResponse(HpcFunctionSearchResult, CommonFunctionMetadata):
    pass


class HpcFunctionPatchRequest(CommonFunctionPatchRequest):
    function_name: str | None = None
    endpoint_ids: list[int] | None = None
