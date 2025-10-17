from src.api.schemas.base import BaseSchema


class HpcDeploymentBase(BaseSchema):
    conda_env_path: str | None = None


class HpcDeploymentCreateRequest(HpcDeploymentBase):
    endpoint_ids: list[int] | None = None


class HpcDeploymentResponse(HpcDeploymentBase):
    id: int
    endpoint_ids: list[int] = []
    user_endpoint_config: dict | None = None


class HpcDeploymentPatchRequest(BaseSchema):
    conda_env_path: str | None = None
    user_endpoint_config: dict | None = None
    endpoint_ids: list[int] | None = None
