from fastapi import APIRouter, Depends, Body, status, HTTPException
from src.api.schemas.modal.modal_app import (
    ModalAppCreateRequest,
    ModalAppMetadataResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, ModalApp
from src.config import Settings, get_settings
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.dependencies.sandboxed_functions import (
    ValidateModalFileProvider,
    DeployModalAppProvider,
)

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

@router.delete(
    "/{id}",
    status_code=status.HTTP_200_OK,
)
async def delete_modal_app(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    # Get the modal app
    # see if it's deletable by the user
    log = logger.bind(id=id)
    modal_app: ModalApp | None = await ModalApp.get(db, id=id)
    if modal_app.owner.identity_id != user.identity_id:
        logger.info(
            f"Failed to delete Modal App (not owned by user)"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to delete or replace (not owned by user {user.username})",
        )
    published_children = [mf for mf in modal_app.modal_functions if mf.doi]
    if len(published_children) > 0:
        published_child_ids = [mf.id for mf in published_children]
        published_child_dois = [mf.doi for mf in published_children]
        logger.info("Failed to delete Modal App (has published children)", child_functions=published_child_ids)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete or replace Modal App {id}. It has published children with DOIs {published_child_dois}",
        )
    
    await db.delete(modal_app)
    await db.commit()
