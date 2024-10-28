from pydantic import Field

from ..shared_function_schemas import CommonFunctionMetadata, CommonFunctionPatchRequest


class ModalFunctionMetadata(CommonFunctionMetadata):
    # Equivalent to "short_name" on entrypoints
    function_name: str
    # Modal functions get a DOI when they are published
    # If they don't have a DOI, they are in draft state
    doi: str | None = None
    # modal supports conda requirements but entrypoints don't
    conda_requirements: list[str] = Field(default_factory=list)


class ModalFunctionMetadataResponse(ModalFunctionMetadata):
    id: int = Field(..., description="The unique identifier for the modal function")
    modal_app_id: int


class ModalFunctionPatchRequest(CommonFunctionPatchRequest):
    doi: str | None = None
    function_name: str | None = None
