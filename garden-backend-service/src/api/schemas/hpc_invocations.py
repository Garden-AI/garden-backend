from datetime import datetime

from pydantic import Field

from src.api.schemas.base import BaseSchema


class HpcInvocationCreateRequest(BaseSchema):
    function_id: int
    endpoint_gcmu_id: str
    globus_task_id: str
    user_endpoint_config: dict = Field(default_factory=dict)


class HpcInvocationResponse(BaseSchema):
    id: int
    user_id: int
    function_id: int
    hpc_endpoint_id: int
    globus_task_id: str
    date_invoked: datetime
    user_endpoint_config: dict
