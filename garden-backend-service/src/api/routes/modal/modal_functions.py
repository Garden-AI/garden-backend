from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.routes._utils import (
    assert_editable_by_user,
)
from src.api.schemas.modal.modal_function import (
    ModalFunctionMetadataResponse,
    ModalFunctionPatchRequest,
)
from src.config import Settings, get_settings
from src.models import ModalFunction, User

logger = get_logger(__name__)
router = APIRouter(prefix="/modal-functions")


@router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ModalFunctionMetadataResponse,
)
async def get_modal_function(
    id: int,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    modal_function = await ModalFunction.get(db, id=id)
    if modal_function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modal Function not found with id {id}",
        )
    return modal_function


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[ModalFunctionMetadataResponse],
)
async def get_modal_functions(
    db: AsyncSession = Depends(get_db_session),
    *,
    id: list[int] | None = Query(None),
    doi: list[str] | None = Query(None),
    tags: list[str] | None = Query(None),
    authors: list[str] | None = Query(None),
    owner_uuid: UUID | None = Query(None),
    draft: bool | None = Query(None),
    year: str | None = Query(None),
    limit: int = Query(50, le=100),
) -> list[ModalFunction]:
    """Fetch multiple modal functions according to query parameters."""
    stmt = select(ModalFunction)

    if id:
        stmt = stmt.where(ModalFunction.id.in_(id))
    if doi:
        stmt = stmt.where(ModalFunction.doi.in_(doi))
    if tags:
        stmt = stmt.where(ModalFunction.tags.overlap(array(tags)))
    if authors:
        stmt = stmt.where(ModalFunction.authors.overlap(array(authors)))
    if owner_uuid:
        stmt = (
            stmt.join(ModalFunction.modal_app)
            .join(User)
            .where(User.identity_id == owner_uuid)
        )
    if draft is not None:
        if draft:
            stmt = stmt.where(ModalFunction.doi == None)  # noqa: E711
        else:
            stmt = stmt.where(ModalFunction.doi != None)  # noqa: E711
    if year:
        stmt = stmt.where(ModalFunction.year == year)

    result = await db.scalars(stmt.limit(limit))
    return list(result.all())


@router.patch("/{id}", response_model=ModalFunctionMetadataResponse)
async def update_modal_function(
    id: int,
    function_data: ModalFunctionPatchRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: User = Depends(authed_user),
):
    log = logger.bind(id=id)
    modal_function: ModalFunction | None = await ModalFunction.get(db, id=id)
    if modal_function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Modal Function with ID {id} found.",
        )

    assert_editable_by_user(modal_function, function_data, user)

    # Don't allow the function to go directly from draft state to archived state
    patch_fields = function_data.model_dump(exclude_none=True)
    #    "was_draft" tells us if this function was in draft state before the patch
    was_draft = modal_function.doi is None
    if was_draft and patch_fields.get("is_archived", False):
        log.warning("Could not archive Modal Function from draft state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot archive a Modal Function in draft state.",
        )

    # Prevent updating certain fields if modal function was already published
    if not was_draft:
        restricted_attrs = [
            attr
            for attr in [
                "doi",
                "function_name",
                "function_text",
            ]
            if attr in patch_fields
        ]
        if restricted_attrs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update a published entrypoint's attribute(s): {', '.join(restricted_attrs)}.",
            )

    # Apply the patch fields and persist the changes
    for key, value in patch_fields.items():
        setattr(modal_function, key, value)
    await db.commit()
    log.info("Updated Modal Function")

    return modal_function
