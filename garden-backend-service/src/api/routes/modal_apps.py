from fastapi import APIRouter, Depends, Body
from typing import Annotated
from src.api.schemas.modal_app import (
    ModalAppCreateRequest,
    ModalAppMetadataResponse,
    ModalAppMetadata,
    ModalFunctionMetadataResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User
from src.config import Settings, get_settings
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.dependencies.sandboxed_functions import ValidateModalFileProvider, DeployModalAppProvider
# from src.sandboxed_functions.modal_publishing_helpers import validate_modal_file, deploy_modal_app

from structlog import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/modal-apps")

validate_modal_file_dep = Depends(ValidateModalFileProvider)
deploy_modal_app_dep = Depends(DeployModalAppProvider)

@router.post("", response_model=ModalAppMetadataResponse)
async def add_modal_app(
    modal_app: ModalAppCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    validate_modal_file: ValidateModalFileProvider = validate_modal_file_dep,
    deploy_modal_app: DeployModalAppProvider = deploy_modal_app_dep,
):
    # First, validate the request. 
    # This includes checking the function metadata provided against the functions present in the App.
    metadata = validate_modal_file(modal_app.file_contents)
    
    # If everything looks good, we will go on to deploy the App.
    prefixed_app_name = f"{user.identity_id}-{modal_app.app_name}"
    deploy_modal_app(
        modal_app.file_contents,
        prefixed_app_name,
        settings.MODAL_TOKEN_ID,
        settings.MODAL_TOKEN_SECRET,
        settings.MODAL_ENV,
    )
    

    # If that worked smoothly within the time limit, we can save the App and its Functions to the DB.
    # (This will happen in the next PR.)
    app_id = "12345678-1234-5678-1234-567812345678" 
    modal_functions = modal_app.modal_functions
    mf = modal_functions[0]
    modal_function_responses = [
        ModalFunctionMetadataResponse(
            **mf.model_dump(exclude_unset=True),
            id="12345678-1234-5678-1234-567812345678",
            parent_app_name=modal_app.app_name,
            parent_app_id=app_id,
        )
    ]

    return ModalAppMetadataResponse(
        **modal_app.model_dump(exclude_unset=True, exclude={"modal_function_names", "modal_functions"}),
        modal_function_names=modal_app.modal_function_names,
        id="23456789",
        owner={"identity_id": "12345678-1234-5678-1234-567812345678"},
        modal_functions=modal_function_responses,
    )