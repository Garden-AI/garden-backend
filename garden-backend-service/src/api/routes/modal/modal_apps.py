from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user, modal_vip
from src.api.dependencies.database import get_db_session
from src.api.dependencies.sandboxed_functions import (
    DeployModalAppProvider,
    ValidateModalFileProvider,
)
from src.api.schemas.modal.modal_app import (
    ModalAppCreateRequest,
    ModalAppMetadataResponse,
)
from src.config import Settings, get_settings
from src.models import ModalApp, User

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
    modal_vip: bool = Depends(modal_vip),
):
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")

    # First, validate the request.
    # This will include checking the function metadata provided against the functions present in the App.
    metadata = validate_modal_file(modal_app.file_contents)

    if metadata["app_name"] != modal_app.app_name:
        raise ValueError("App name in metadata does not match the provided app name")

    if set(metadata["function_names"]) != set(modal_app.modal_function_names):
        raise ValueError(
            "Function names in metadata do not match the provided function names"
        )

    # If everything looks good, we will go on to deploy the App.
    prefixed_app_name = f"{user.identity_id}-{modal_app.app_name}"

    # TODO: set a timeout for this and/or make it async
    deploy_modal_app(
        modal_app.file_contents,
        prefixed_app_name,
        settings.MODAL_TOKEN_ID,
        settings.MODAL_TOKEN_SECRET,
        settings.MODAL_ENV,
    )

    model_dict = modal_app.model_dump(
        exclude={"modal_function_names", "owner_identity_id", "id"}, exclude_unset=True
    )
    model_dict["user_id"] = user.id
    modal_app_db_model = ModalApp.from_dict(model_dict)

    db.add(modal_app_db_model)
    await db.commit()
    return modal_app_db_model


@router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ModalAppMetadataResponse,
)
async def get_modal_app(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    modal_vip: bool = Depends(modal_vip),
):
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")

    modal_app = await ModalApp.get(db, id=id)
    if modal_app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modal App not found with id {id}",
        )
    return modal_app
