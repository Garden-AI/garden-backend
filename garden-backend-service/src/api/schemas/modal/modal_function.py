from ..shared_function_schemas import CommonFunctionMetadata, CommonFunctionPatchRequest


class ModalFunctionMetadata(CommonFunctionMetadata):
    # Modal functions get a DOI when they are published
    # If they don't have a DOI, they are in draft state
    doi: str | None
    # Equivalent to "short_name" on entrypoints
    function_name: str


class ModalFunctionMetadataResponse(ModalFunctionMetadata):
    id: int
    modal_app_id: int


class ModalFunctionPatchRequest(CommonFunctionPatchRequest):
    doi: str | None = None
    function_name: str | None = None
