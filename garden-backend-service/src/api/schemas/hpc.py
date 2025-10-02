from pydantic import Field

from src.api.schemas.base import BaseSchema
from src.api.schemas.shared_function_schemas import (
    CommonFunctionMetadata,
    CommonFunctionPatchRequest,
)


class HpcFunctionCreateRequest(CommonFunctionMetadata):
    function_name: str
    deployment_ids: list[int]


class HpcFunctionDeploymentInfo(BaseSchema):
    deployment_ids: list[int]
    endpoint_name: str
    endpoint_gcmu_id: str


class HpcFunctionMetadataResponse(CommonFunctionMetadata):
    id: int
    function_name: str
    available_deployments: list[HpcFunctionDeploymentInfo] = Field(default_factory=list)
    available_endpoints: list[str] = Field(default_factory=list)
    num_invocations: int = 0


class HpcFunctionPatchRequest(CommonFunctionPatchRequest):
    function_name: str | None = None
    deployment_ids: list[int] | None = None
