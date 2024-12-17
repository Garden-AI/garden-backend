from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user, in_modal_publishers_group
from src.api.dependencies.database import get_db_session
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
from src.modal.utils import monitor_modal_deployment
from src.models import Garden, ModalApp, ModalFunction, User
from src.models._associations import gardens_modal_functions

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
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")

    # Parse and validate the modal file content -
    # i.e. the metadata in the request body is faithful to its file_contents
    _validate_modal_app_metadata(modal_app)
    logger.info("Validated modal file metadata consistency")

    # we also need to persist hardware_specs for each function in order to
    # estimate usage. So we extract them by importing the app object in a sandboxed environment
    sandbox_metadata = validate_modal_file({"file_contents": modal_app.file_contents})
    hardware_specs: dict[str, dict] = sandbox_metadata["functions"]

    # Finally, we deploy the App.
    prefixed_app_name = f"{user.identity_id}-{modal_app.app_name}"
    model_dict = modal_app.model_dump(
        exclude={
            "modal_function_names",
            "owner_identity_id",
            "id",
            "overwrite_existing",
        },
        exclude_unset=True,
    )

    if existing_modal_app := await ModalApp.get(
        db, app_name=prefixed_app_name, user_id=user.id
    ):
        if modal_app.overwrite_existing:
            for modal_fn in model_dict["modal_functions"]:
                modal_fn["hardware_spec"] = hardware_specs[modal_fn["function_name"]]
            existing_modal_app.modal_functions = [
                ModalFunction.from_dict(modal_fn)
                for modal_fn in model_dict["modal_functions"]
            ]
            await db.commit()
            return existing_modal_app
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Modal App with name: {modal_app.app_name} already exists. Set the 'overwrite_existing' parameter to 'true' to enable overwriting.",
            )

    deploy_modal_app(
        {
            "app_name": prefixed_app_name,
            "env": settings.MODAL_ENV,
            "file_contents": modal_app.file_contents,
            "token_id": settings.MODAL_TOKEN_ID,
            "token_secret": settings.MODAL_TOKEN_SECRET,
        }
    )

    model_dict["user_id"] = user.id
    model_dict["app_name"] = prefixed_app_name
    for modal_fn in model_dict["modal_functions"]:
        name = modal_fn["function_name"]
        modal_fn["hardware_spec"] = hardware_specs[name]

    modal_app_db_model = ModalApp.from_dict(model_dict)

    db.add(modal_app_db_model)
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
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")

    _validate_modal_app_metadata(modal_app)
    logger.info("Validated modal file metadata consistency")

    # we also need to persist hardware_specs for each function in order to
    # estimate usage. So we extract them by importing the app object in a sandboxed environment
    sandbox_metadata = validate_modal_file({"file_contents": modal_app.file_contents})
    hardware_specs: dict[str, dict] = sandbox_metadata["functions"]

    # If everything looks good, we will go on to deploy the App.
    prefixed_app_name = f"{user.identity_id}-{modal_app.app_name}"
    # add a unique suffix so we can deploy to modal without clobbering the old app
    full_app_name = f"{prefixed_app_name}-{uuid4()}"
    model_dict = modal_app.model_dump(
        exclude={
            "modal_function_names",
            "owner_identity_id",
            "id",
            "overwrite_existing",
        },
        exclude_unset=True,
    )

    existing_modal_app = await db.scalar(
        select(ModalApp)
        .where(ModalApp.user_id == user.id)
        .filter(ModalApp.app_name.ilike(f"{prefixed_app_name}%"))
        .order_by(ModalApp.version.desc())
    )

    logger.info("Existing Modal App", existing_modal_app=existing_modal_app)

    if existing_modal_app is not None:
        if modal_app.overwrite_existing:
            _raise_if_undeletable(existing_modal_app, user, logger)
            logger.info(
                "Overwriting existing modal app.", modal_app_name=prefixed_app_name
            )
            # TODO Rethink this behavior
            # find the associated garden and mark it as archived
            gmfs = await db.scalars(
                select(gardens_modal_functions.c.garden_id).where(
                    gardens_modal_functions.c.modal_function_id
                    == existing_modal_app.modal_functions[0].id
                )
            )
            if garden_id := gmfs.first():
                if garden := await Garden.get(db, id=garden_id):
                    garden.is_archived = True
        else:
            raise ModalException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to overwrite modal app.",
                suggested_fix="Set 'overwrite_existing' to 'true' to enable overwriting.",
            )

    # Deploy the new modal app
    model_dict["user_id"] = user.id
    model_dict["app_name"] = full_app_name
    for modal_fn in model_dict["modal_functions"]:
        modal_fn["hardware_spec"] = hardware_specs[modal_fn["function_name"]]
    modal_app_db_model = ModalApp.from_dict(model_dict)

    db.add(modal_app_db_model)
    await db.commit()

    deploy_config = {
        "app_name": prefixed_app_name,
        "env": settings.MODAL_ENV,
        "file_contents": modal_app.file_contents,
        "token_id": settings.MODAL_TOKEN_ID,
        "token_secret": settings.MODAL_TOKEN_SECRET,
    }

    background_tasks.add_task(
        monitor_modal_deployment,
        deploy_modal_app,
        deploy_config,
        modal_app_db_model,
        settings,
    )

    return modal_app_db_model


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
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")

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

    _raise_if_undeletable(modal_app, user, log)

    await db.delete(modal_app)
    await db.commit()
    log.info("Deleted Modal App from database")
    return {"detail": f"Successfully deleted garden with id {id}."}


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
