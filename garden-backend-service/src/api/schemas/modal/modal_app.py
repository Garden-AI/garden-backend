from uuid import UUID

from pydantic import AliasPath, Field, computed_field

from src.modal.utils import AsyncModalJobStatus

from ..base import BaseSchema
from .modal_function import ModalFunctionMetadata, ModalFunctionMetadataResponse


class ModalAppMetadata(BaseSchema):
    app_name: str
    original_app_name: str | None = None
    modal_functions: list[ModalFunctionMetadata] = Field(default_factory=list)
    file_contents: str

    requirements: list[str] = Field(default_factory=list)
    conda_requirements: list[str] = Field(default_factory=list)

    base_image_name: str

    @computed_field
    @property
    def modal_function_names(self) -> list[str]:
        return [mf.function_name for mf in self.modal_functions]


class ModalAppCreateRequest(ModalAppMetadata):
    owner_identity_id: str | None = None


class ModalAppMetadataResponse(ModalAppMetadata):
    owner_identity_id: UUID = Field(alias=AliasPath("owner", "identity_id"))
    id: int = Field(..., description="The unique identifier for the modal app")
    modal_functions: list[ModalFunctionMetadataResponse] = Field(default_factory=list)

    @computed_field
    @property
    def modal_function_ids(self) -> list[int]:
        return [mf.id for mf in self.modal_functions]


class AsyncModalAppMetadataResponse(ModalAppMetadataResponse):
    deploy_status: AsyncModalJobStatus | None = None
    deploy_error: str | None = None


class ModalFileMetadataRequest(BaseSchema):
    file_contents: str


class ModalFileMetadataResponse(ModalAppMetadata):
    # successful POST /modal-file-metadata response should have everything needed for the subsequent CreateRequest
    pass
