from fastapi import APIRouter, Depends, Body, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, ModalFunction
from src.config import Settings, get_settings
from src.api.dependencies.auth import authed_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.modal.modal_function import (
    ModalFunctionMetadataResponse,
    ModalFunctionPatchRequest,
)

from structlog import get_logger

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
    user: User = Depends(authed_user),
    settings: Settings = Depends(get_settings),
):
    if not settings.MODAL_ENABLED:
        raise NotImplementedError("Garden's Modal integration has not been enabled")
    
    modal_function = await ModalFunction.get(db, id=id)
    if modal_function is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modal Function not found with id {id}",
        )
    return modal_function

@router.patch("/{doi:path}", response_model=ModalFunctionMetadataResponse)
async def update_modal_function(
    id: int,
    function_data: ModalFunctionPatchRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: User = Depends(authed_user),
):
    pass