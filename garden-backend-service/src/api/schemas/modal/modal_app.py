from uuid import UUID

from pydantic import AliasPath, Field, computed_field

from ..base import BaseSchema
from .modal_function import ModalFunctionMetadata, ModalFunctionMetadataResponse


class ModalAppMetadata(BaseSchema):
    app_name: str
    modal_function_names: list[str] = Field(default_factory=list)
    file_contents: str

    requirements: list[str] = Field(default_factory=list)
    base_image_name: str


class ModalAppCreateRequest(ModalAppMetadata):
    owner_identity_id: str | None = None
    modal_functions: list[ModalFunctionMetadata] = Field(default_factory=list)


class ModalAppMetadataResponse(ModalAppMetadata):
    owner_identity_id: UUID = Field(alias=AliasPath("owner", "identity_id"))
    id: int
    modal_functions: list[ModalFunctionMetadataResponse] = Field(default_factory=list)

    @computed_field
    @property
    def modal_function_ids(self) -> list[str]:
        return [mf.doi for mf in self.modal_functions]
