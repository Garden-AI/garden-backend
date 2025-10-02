from src.api.schemas.base import BaseSchema


class HpcDeploymentBase(BaseSchema):
    conda_env_path: str | None = None


class HpcDeploymentCreateRequest(HpcDeploymentBase):
    pass


class HpcDeploymentResponse(HpcDeploymentBase):
    id: int


class HpcDeploymentPatchRequest(BaseSchema):
    name: str | None = None
    conda_env_path: str | None = None
