from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.database import get_db_session
from src.api.dependencies.search import query_mdf_search
from src.api.schemas.mdf.dataset import AccelerateDatasetMetadata, MDFSearchResponse
from src.api.schemas.search.globus_search import GSearchRequestBody
from src.config import Settings, get_settings
from src.models import Dataset

logger = getLogger(__name__)

router = APIRouter(prefix="/mdf")


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
)
async def search_datasets(
    request: GSearchRequestBody,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MDFSearchResponse:
    """
    Accepts Globus GSearchRequest in request body.
    Acts as an intermediary for querying MDF's globus search index and then augments the query results with
    any accelerate metadata stored in the garden backend (connected_entrypoints, owner_identity_id, etc..)

    Does not require user auth since MDF search index also does not require auth.
    Does not support globus search scroll queries.
    """

    response = await query_mdf_search(
        request.model_dump(exclude_unset=True, exclude_none=True), settings
    )
    if response.status_code == 200:
        result = MDFSearchResponse(**response.json())

        for gmeta in result.gmeta:
            versioned_source_id = gmeta.root.subject
            dataset: Dataset | None = await Dataset.get(
                db, versioned_source_id=versioned_source_id
            )
            if dataset:
                gmeta.root.accelerate_metadata = AccelerateDatasetMetadata(
                    **dataset.get_accelerate_metadata()
                )

        return result
    else:
        # Pass on search error if response code is not 200
        logger.warning(
            msg=f"MDF search query returned status code {response.status_code}"
        )
        raise HTTPException(status_code=response.status_code, detail=response.json())
