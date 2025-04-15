from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from modal_proto import api_pb2
from sqlalchemy import select
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
from src.api.routes._utils import assert_editable_by_user
from src.api.schemas.modal.modal_app import (
    AsyncModalAppMetadataResponse,
    ModalAppCreateRequest,
    ModalAppMetadataResponse,
    ModalAppPatchRequest,
    ModalFileMetadataRequest,
)
from src.config import Settings, get_settings
from src.exceptions.modal import ModalException
from src.modal import parse_modal_file
from src.modal.status import AsyncModalJobStatus
from src.modal.utils import monitor_modal_deployment
from src.models import ModalApp, ModalFunction, User

from .modal_file_metadata import parse_modal_file_metadata

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
    # get app id from deployment if successful
    app_id = await _deploy_modal_app_helper(
        deploy_modal_app, full_app_name, modal_app, settings
    )
    modal_app_db_model.modal_app_id = app_id
    await db.commit()

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


@router.patch("/async/{id}", response_model=AsyncModalAppMetadataResponse)
async def patch_modal_app(
    id: int,
    patch_request: ModalAppPatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
    validate_modal_file: ValidateModalFileProvider = validate_modal_file_dep,
    deploy_modal_app: DeployModalAppProvider = deploy_modal_app_dep,
):
    """Update a modal app's metadata in-place."""
    modal_app = await ModalApp.get(db, id=id)
    if modal_app is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modal App not found with id {id}",
        )

    assert_editable_by_user(modal_app, patch_request, user)
    # Update other metadata fields provided in request
    patch_fields = patch_request.model_dump(
        exclude_none=True, exclude={"file_contents"}
    )
    for key, value in patch_fields.items():
        setattr(modal_app, key, value)

    if patch_request.file_contents is None:
        # if no changes to file contents, return without re-deploying
        return modal_app
    else:
        modal_app.deploy_status = AsyncModalJobStatus.PENDING
        modal_app.deploy_error = None
        modal_app.file_contents = patch_request.file_contents

    # otherwise, do a "full publishing flow" with some extra validation
    existing_functions = {fn.function_name: fn for fn in modal_app.modal_functions}

    # TODO: required_names only needs to be functions actually in use
    required_names = set(existing_functions.keys())

    # collect function names from the updated file_contents
    parsed_metadata = await parse_modal_file_metadata(
        ModalFileMetadataRequest(file_contents=patch_request.file_contents)
    )
    parsed_fn_names = {fn.function_name for fn in parsed_metadata.modal_functions}
    # updated app must not remove any functions in use
    if missing_names := required_names - parsed_fn_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Function names ({', '.join(missing_names)}) not found in the updated Modal file, but are in use by one or more Gardens.",
        )

    if parsed_metadata.app_name != modal_app.original_app_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App name mismatch: Got '{parsed_metadata.app_name}' from file but expected '{modal_app.original_app_name}'.",
        )

    # app looks valid, continue to deploying the app
    sandbox_metadata = await validate_modal_file(
        {"file_contents": patch_request.file_contents}
    )
    hardware_specs = sandbox_metadata["functions"]

    # update existing functions or create new ones in the db
    # TODO: delete functions that are not in use nor present in updated app
    for modal_fn_meta in parsed_metadata.modal_functions:
        name = modal_fn_meta.function_name
        fn_data = modal_fn_meta.model_dump(exclude={"file_contents"})
        # ensure up-to-date hardware spec
        if "." in name:
            class_name, _ = name.split(".")
            # methods will share the same hardware spec as the special
            # "class.*" modal function
            fn_data["hardware_spec"] = hardware_specs[f"{class_name}.*"]
        else:
            fn_data["hardware_spec"] = hardware_specs[name]
        # update existing function or create new one
        if name in existing_functions:
            # update the existing function with the new metadata
            for field, value in fn_data.items():
                setattr(existing_functions[name], field, value)
        else:
            # create a new function
            new_fn = ModalFunction.from_dict(fn_data)
            modal_app.modal_functions.append(new_fn)

    await db.commit()
    await db.refresh(modal_app)
    # finally, redeploy the app
    deploy_config = {
        "app_name": modal_app.app_name,
        "env": settings.MODAL_ENV,
        "file_contents": patch_request.file_contents,
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
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[AsyncModalAppMetadataResponse],
)
async def get_modal_apps(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(authed_user),
):
    """Get all of the current user's Modal Apps"""
    query = (
        select(ModalApp).where(ModalApp.user_id == user.id).order_by(ModalApp.id.desc())
    )
    result = await db.execute(query)
    modal_apps = result.scalars().all()
    logger.info(f"Found {len(modal_apps)} modal apps for user {user.id}")
    return modal_apps


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
    app_id = modal_app.modal_app_id
    _raise_if_undeletable(modal_app, user, log)
    try:
        await db.delete(modal_app)
        log.info("Deleted Modal App from database")
        await _stop_modal_app(app_name, modal_client, settings, app_id)
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
) -> str:
    result = await deploy_modal_app(
        {
            "app_name": full_app_name,
            "env": settings.MODAL_ENV,
            "file_contents": modal_app.file_contents,
            "token_id": settings.MODAL_TOKEN_ID,
            "token_secret": settings.MODAL_TOKEN_SECRET,
        }
    )
    return result["app_id"]


async def _lookup_app_id(
    app_name: str, modal_client: modal.client._Client, settings: Settings
) -> str | None:
    """Look up an app ID from Modal using AppListRequest.

    This is more reliable than AppGetByDeploymentNameRequest as it searches
    through all apps in the environment.
    """
    request = api_pb2.AppListRequest(
        environment_name=settings.MODAL_ENV,
    )
    response = await retry_transient_errors(modal_client.stub.AppList, request)

    for app in response.apps:
        if app.name == app_name:
            return app.app_id
    return None


async def _stop_modal_app(
    app_name: str,
    modal_client: modal.client._Client,
    settings: Settings,
    app_id: str | None = None,
):
    if app_id is None:
        app_id = await _lookup_app_id(app_name, modal_client, settings)
        if app_id is None:
            logger.warning(
                f"Could not find app ID for {app_name}, skipping stop request"
            )
            return

    # Stop the app
    stop_request = api_pb2.AppStopRequest(
        app_id=app_id,
        source=api_pb2.APP_STOP_SOURCE_PYTHON_CLIENT,
    )
    await retry_transient_errors(modal_client.stub.AppStop, stop_request)
