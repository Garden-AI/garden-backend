from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.auth import mdf_authenticated
from src.api.dependencies.database import get_db_session
from src.api.schemas.mdf.dataset import MDFDatasetCreateRequest
from src.auth.auth_state import MDFAuthenticationState
from src.config import Settings, get_settings
from src.models import PendingMDFFlow

router = APIRouter(prefix="/mdf")
logger = getLogger(__name__)


@router.put("/create", status_code=status.HTTP_200_OK)
async def add_pending_dataset(
    new_dataset: MDFDatasetCreateRequest,
    mdf_auth: MDFAuthenticationState = Depends(mdf_authenticated),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """
    Adds pending MDF dataset to `pending-mdf-datasets` table.

    Any records in `pending-mdf-datasets` table will be polled periodically by the background task check_active_mdf_flows.
    When the background task sees that the dataset has finished publishing,
    the pending record will be removed and a new MDF dataset record will be created.

    The route will only accept requests with MDF client cred auth. Meant to be only be called from the MDF connect server.
    """

    if settings.MDF_POLL_FLOWS:
        new_pending_flow = PendingMDFFlow(
            flow_action_id=new_dataset.flow_action_id,
            versioned_source_id=new_dataset.versioned_source_id,
            owner_identity_id=new_dataset.owner_identity_id,
            previous_versions=new_dataset.previous_versions,
        )
        db.add(new_pending_flow)

        try:
            await db.commit()
            logger.info(
                msg=f"Added MDF background task for flow {new_dataset.flow_action_id}"
            )
            return {
                "detail": f"Added flow {new_dataset.flow_action_id} to background tasks."
            }
        except IntegrityError as e:
            await db.rollback()
            logger.warning(
                msg=f"Failed to add MDF background task for flow {new_dataset.flow_action_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to add flow {new_dataset.flow_action_id} to background tasks.",
            ) from e
    else:
        return {
            "detail": "Polling MDF flows is currently turned off, did not add flow to background tasks."
        }
