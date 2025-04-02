from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from modal_proto import api_pb2
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

import modal
from modal._utils.grpc_utils import retry_transient_errors
from src.api.dependencies.auth import (
    authed_user,
    in_modal_publishers_group,
    is_super_user,
)
from src.api.dependencies.database import get_db_session
from src.api.dependencies.modal import get_modal_client
from src.api.dependencies.sandboxed_functions import (
    DeployModalAppProvider,
    ValidateModalFileProvider,
)
from src.api.schemas.modal.modal_app import (
    AsyncModalAppMetadataResponse,
    ModalAppCreateRequest,
    ModalAppMetadataResponse,
)
from src.config import Settings, get_settings
from src.exceptions.modal import ModalException
from src.modal import parse_modal_file
from src.modal.status import AsyncModalJobStatus
from src.modal.utils import monitor_modal_deployment
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
    in_modal_publishers_group: bool = Depends(in_modal_publishers_group),
):
    hardware_specs = await _validate_modal_app_metadata_helper(
        modal_app, validate_modal_file
    )
    full_app_name = _generate_app_name(user, modal_app.app_name)
    original_app_name = modal_app.app_name

    modal_app_db_model = await _save_modal_app_to_db(
        db, modal_app, user, full_app_name, original_app_name, hardware_specs
    )

    await _deploy_modal_app_helper(deploy_modal_app, full_app_name, modal_app, settings)

    return modal_app_db_model


@router.post("/async", response_model=AsyncModalAppMetadataResponse)
async def add_modal_app_async(
    modal_app: ModalAppCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    validate_modal_file: ValidateModalFileProvider = validate_modal_file_dep,
    deploy_modal_app: DeployModalAppProvider = deploy_modal_app_dep,
    in_modal_publishers_group: bool = Depends(in_modal_publishers_group),
):
    hardware_specs = await _validate_modal_app_metadata_helper(
        modal_app, validate_modal_file
    )
    original_app_name = modal_app.app_name
    full_app_name = _generate_app_name(user, modal_app.app_name)
    modal_app_db_model = await _save_modal_app_to_db(
        db, modal_app, user, full_app_name, original_app_name, hardware_specs
    )

    deploy_config = {
        "app_name": full_app_name,
        "env": settings.MODAL_ENV,
        "file_contents": modal_app.file_contents,
        "token_id": settings.MODAL_TOKEN_ID,
        "token_secret": settings.MODAL_TOKEN_SECRET,
    }
    background_tasks.add_task(
        monitor_modal_deployment,
        deploy_modal_app,
        deploy_config,
        modal_app_db_model.id,
        settings,
    )

    return modal_app_db_model


@router.post("/redeploy/{id}", response_model=AsyncModalAppMetadataResponse)
async def redeploy_modal_app(
    id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    deploy_modal_app: DeployModalAppProvider = deploy_modal_app_dep,
    _is_super_user: bool = Depends(is_super_user),
):
    """Redeploy a modal app in-place. Only available to super users."""
    modal_app = await ModalApp.get(db, id=id)
    if modal_app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modal App not found with id {id}",
        )

    # reset deploy status to pending
    modal_app.deploy_status = AsyncModalJobStatus.PENDING
    modal_app.deploy_error = None
    await db.commit()

    deploy_config = {
        "app_name": modal_app.app_name,
        "env": settings.MODAL_ENV,
        "file_contents": modal_app.file_contents,
        "token_id": settings.MODAL_TOKEN_ID,
        "token_secret": settings.MODAL_TOKEN_SECRET,
    }

    background_tasks.add_task(
        monitor_modal_deployment,
        deploy_modal_app,
        deploy_config,
        modal_app.id,
        settings,
    )

    return modal_app


def _validate_modal_app_metadata(app_metadata: ModalAppCreateRequest):
    """Validate that the metadata in the request matches what we parse from the modal file.

    Args:
        app_metadata: The app metadata from the request body

    Raises:
        ModalException: If there are inconsistencies between the metadata and parsed file
    """
    parse_results = parse_modal_file(app_metadata.file_contents)

    if len(parse_results.apps) != 1:
        raise ModalException(
            detail=f"Invalid modal file: Found {len(parse_results.apps)} App objects. Expected exactly one.",
            suggested_fix="Submit a file with a single modal App object.",
        )

    app_info = parse_results.apps[0]

    # Validate app name matches
    if app_info.app_name != app_metadata.app_name:
        raise ModalException(
            detail=f"App name mismatch: Got '{app_info.app_name}' from file but '{app_metadata.app_name}' in request.",
            suggested_fix="Ensure the App name in your modal file matches the metadata.",
        )

    # Validate base image name
    if app_info.image.base_image != app_metadata.base_image_name:
        raise ModalException(
            detail=f"Base image mismatch: Got '{app_info.image.base_image}' from file but '{app_metadata.base_image_name}' in request.",
            suggested_fix="Ensure the base image in your modal file matches the metadata.",
        )

    # confirm function names match
    request_function_names = {fn.function_name for fn in app_metadata.modal_functions}
    file_function_names = {fn.function_name for fn in parse_results.functions}

    if not request_function_names:
        raise ModalException(
            detail="No function names provided",
            suggested_fix="Must provide names of functions to expose in request to create Modal App",
        )
    if not request_function_names <= file_function_names:
        diff = request_function_names - file_function_names
        raise ModalException(
            detail=f"Function names ({', '.join(diff)}) are not present in the Modal file",
            suggested_fix="Make sure function names in the Modal App creation request match the function names in the Modal file",
        )
    return


@router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=AsyncModalAppMetadataResponse,
)
async def get_modal_app(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    modal_app = await ModalApp.get(db, id=id, order_by="version")
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
    modal_client=Depends(get_modal_client),
):
    # Get the modal app
    # see if it's deletable by the user
    log = logger.bind(id=id)
    modal_app: ModalApp | None = await ModalApp.get(db, id=id)
    if not modal_app:
        log.info("No Modal App to delete")
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail=f"No Modal App found with id {id}.",
        )

    app_name = modal_app.app_name
    _raise_if_undeletable(modal_app, user, log)
    try:
        await db.delete(modal_app)
        log.info("Deleted Modal App from database")
        await _stop_modal_app(app_name, modal_client, settings)
        log.info("stopped app on modal")
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping app on modal: {str(e)}",
        )
    await db.commit()
    return {"detail": f"Successfully deleted modal app with id {id}."}


def _raise_if_undeletable(modal_app, user, log):
    if modal_app.owner.identity_id != user.identity_id:
        log.info("Failed to delete Modal App (not owned by user)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to delete or replace (not owned by user {user.username})",
        )
    published_children = [mf for mf in modal_app.modal_functions if mf.doi]
    if len(published_children) > 0:
        published_child_ids = [mf.id for mf in published_children]
        published_child_dois = [mf.doi for mf in published_children]
        log.info(
            "Failed to delete Modal App (has published children)",
            child_functions=published_child_ids,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete or replace Modal App {id}. It has published children with DOIs {published_child_dois}",
        )


async def _validate_modal_app_metadata_helper(
    modal_app: ModalAppCreateRequest, validate_modal_file
):
    _validate_modal_app_metadata(modal_app)
    logger.info("Validated modal file metadata consistency")
    sandbox_metadata = await validate_modal_file(
        {"file_contents": modal_app.file_contents}
    )
    hardware_specs = sandbox_metadata["functions"]
    return hardware_specs


def _generate_app_name(user: User, app_name: str) -> str:
    """Generate a unique app name for deployment to Modal.

    The app names look like: <user_id>-<app_name>-<unique-suffix>

    Note: Modal limits app names to 64 characters. To give our users
    the freedom to name their apps within Modal's guidelines, this function
    will truncate the user supplied app name to fit within the size limit before
    we deploy to our Modal environment.
    """
    modal_max_app_name_size = 64
    prefix_len = len(str(user.identity_id))
    suffix_len = 8
    max_app_name_len = modal_max_app_name_size - (
        prefix_len + suffix_len + 2  # 2 for separators
    )

    # truncate the app name if it is too long
    app_name = (
        app_name if len(app_name) < max_app_name_len else app_name[:max_app_name_len]
    )
    prefixed_app_name = f"{user.identity_id}-{app_name}"

    # generate a unique suffix
    suffix = str(uuid4())[:suffix_len]
    full_app_name = f"{prefixed_app_name}-{suffix}"
    return full_app_name


async def _save_modal_app_to_db(
    db: AsyncSession,
    modal_app: ModalAppCreateRequest,
    user: User,
    full_app_name: str,
    original_app_name: str,
    hardware_specs: dict[str, dict[str, Any]],
):
    model_dict = modal_app.model_dump(
        exclude={
            "modal_function_names",
            "owner_identity_id",
            "id",
        },
        exclude_unset=True,
    )
    model_dict["user_id"] = user.id
    model_dict["app_name"] = full_app_name
    model_dict["original_app_name"] = original_app_name
    for modal_fn in model_dict["modal_functions"]:
        name = modal_fn["function_name"]
        if "." in name:
            class_name, method_name = name.split(".")
            # methods will share the same hardware spec as the special
            # "class.*" modal function
            modal_fn["hardware_spec"] = hardware_specs[f"{class_name}.*"]
        else:
            modal_fn["hardware_spec"] = hardware_specs[name]
        if "file_contents" in modal_fn:
            # redundant with app contents but part of schema
            del modal_fn["file_contents"]

    modal_app_db_model = ModalApp.from_dict(model_dict)
    db.add(modal_app_db_model)
    await db.commit()
    return modal_app_db_model


async def _deploy_modal_app_helper(
    deploy_modal_app,
    full_app_name: str,
    modal_app: ModalAppCreateRequest,
    settings: Settings,
):
    await deploy_modal_app(
        {
            "app_name": full_app_name,
            "env": settings.MODAL_ENV,
            "file_contents": modal_app.file_contents,
            "token_id": settings.MODAL_TOKEN_ID,
            "token_secret": settings.MODAL_TOKEN_SECRET,
        }
    )


async def _stop_modal_app(
    app_name: str, modal_client: modal.client._Client, settings: Settings
):
    # Get the app id from the app name
    id_request = api_pb2.AppGetByDeploymentNameRequest(
        namespace=api_pb2.DEPLOYMENT_NAMESPACE_WORKSPACE,
        name=app_name,
        environment_name=settings.MODAL_ENV,
    )
    id_response = await retry_transient_errors(
        modal_client.stub.AppGetByDeploymentName, id_request
    )
    # Stop the app
    stop_request = api_pb2.AppStopRequest(
        app_id=id_response.app_id,
        source=api_pb2.APP_STOP_SOURCE_PYTHON_CLIENT,
    )
    await retry_transient_errors(modal_client.stub.AppStop, stop_request)
