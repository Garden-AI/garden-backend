from datetime import datetime
from uuid import UUID

from pydantic import AliasPath, Field, computed_field

from .base import BaseSchema, UniqueList
from .modal_function import ModalFunctionMetadataResponse, ModalFunctionMetadata

class ModalAppMetadata(BaseSchema):
    app_name: str
    version: str = "0.0.1"
    modal_function_names: list[str] = Field(default_factory=list)
    file_contents: str

    is_archived: bool = False

    requirements: list[str] = Field(default_factory=list)
    base_image_name: str


class ModalAppCreateRequest(ModalAppMetadata):
    # Really this request will need the function metadata all bundled in, right?
    # modal_function_ids: UniqueList[str] = Field(default_factory=list)
    owner_identity_id: UUID | None = None
    modal_functions: list[ModalFunctionMetadata] = Field(default_factory=list)


class ModalAppMetadataResponse(ModalAppMetadata):
    owner_identity_id: UUID = Field(alias=AliasPath("owner", "identity_id"))
    id: int
    modal_functions: list[ModalFunctionMetadataResponse] = Field(default_factory=list)

    @computed_field
    @property
    def modal_function_ids(self) -> list[str]:
        return [mf.doi for mf in self.modal_functions]