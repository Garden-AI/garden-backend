from typing import Any

from pydantic import Field

from src.api.schemas.base import BaseSchema, UniqueList
from src.models.functions.hpc.hpc_deployments import DeploymentType


class HpcDeploymentBase(BaseSchema):
    name: str
    description: str | None = None
    deployment_type: DeploymentType

    # Conda fields (for existing environments)
    conda_env_name: str | None = None
    conda_env_path: str | None = None
    conda_requirements: dict[str, Any] | None = None

    # Python dependencies used by uv envs
    python_dependencies: UniqueList[str] | None = Field(default_factory=list)


class HpcDeploymentCreateRequest(HpcDeploymentBase):
    pass


class HpcDeploymentResponse(HpcDeploymentBase):
    id: int


class HpcDeploymentPatchRequest(BaseSchema):
    name: str | None = None
    description: str | None = None
    conda_env_name: str | None = None
    conda_env_path: str | None = None
    conda_requirements: dict[str, Any] | None = None
    python_dependencies: UniqueList[str] | None = None
