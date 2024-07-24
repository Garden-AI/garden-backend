from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.dependencies.database import get_db_session
from src.api.schemas.failed_search_index_update import FailedSearchIndexUpdateResponse
from src.models import FailedSearchIndexUpdate

router = APIRouter(prefix="/status")


@router.get("/failed-updates", response_model=list[FailedSearchIndexUpdateResponse])
async def get_failed_updates(
    db: AsyncSession = Depends(get_db_session),
) -> list[FailedSearchIndexUpdate]:
    """Fetch Failed Search Index Updates"""
    failed_updates = await db.scalars(select(FailedSearchIndexUpdate))
    return failed_updates.all()
