from datetime import datetime

from fastapi import APIRouter, Depends, status
from structlog import get_logger

from src.api.dependencies.auth import authed_user, in_modal_publishers_group
from src.api.schemas.modal.modal_app import (
    ModalFileMetadataRequest,
    ModalFileMetadataResponse,
)
from src.api.schemas.modal.modal_function import ModalFunctionMetadata
from src.config import Settings, get_settings
from src.exceptions.modal import ModalException
from src.modal.user_file_parsing import ModalFileParseResults, parse_modal_file
from src.models import User

logger = get_logger(__name__)
router = APIRouter(prefix="/modal-file-metadata")


@router.post("", response_model=ModalFileMetadataResponse)
async def parse_modal_file_metadata(
    request: ModalFileMetadataRequest,
    settings: Settings = Depends(get_settings),
    user: User = Depends(authed_user),
    _modal_vip: bool = Depends(in_modal_publishers_group),
):
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")

    results: ModalFileParseResults = parse_modal_file(request.file_contents)
    logger.info("Validated user modal file")

    function_metas = []
    for fn in results.functions:
        meta = ModalFunctionMetadata(
            function_name=fn.function_name,
            function_text=fn.function_text,
            file_contents=request.file_contents,
            title=fn.function_name,
            description=fn.function_desc,
            year=str(datetime.now().year),
            requirements=fn.image.pip_requirements,
            conda_requirements=fn.image.conda_requirements,
        )
        for local_ep in results.local_entrypoints:
            if fn.function_name in local_ep.called_functions:
                meta.test_functions += [local_ep.function_text]
        function_metas += [meta]

    if len(results.apps) != 1:
        raise ModalException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid modal file: user code should define exactly one App object. Found {len(results.apps)} App objects.",
            suggested_fix="Submit a file with a single modal `App`.",
        )

    app_info = results.apps[0]

    response = ModalFileMetadataResponse(
        app_name=app_info.app_name,
        base_image_name=app_info.image.base_image,
        file_contents=request.file_contents,
        modal_functions=function_metas,
        requirements=app_info.image.pip_requirements,
        conda_requirements=app_info.image.conda_requirements,
    )

    return response
