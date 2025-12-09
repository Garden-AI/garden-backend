from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies.auth import is_super_user
from src.api.dependencies.database import get_db_session
from src.api.schemas.benchmark import BenchmarkResultCreate, BenchmarkResultResponse
from src.models.benchmark import BenchmarkResult

router = APIRouter(prefix="/benchmarks")
logger = get_logger(__name__)


@router.get("", response_model=list[BenchmarkResultResponse])
async def get_benchmark_results(
    db: AsyncSession = Depends(get_db_session),
):
    """Get all benchmark results."""
    query = select(BenchmarkResult).order_by(BenchmarkResult.timestamp.desc())
    results = await db.scalars(query)
    return results.all()


@router.post(
    "", response_model=BenchmarkResultResponse, status_code=status.HTTP_201_CREATED
)
async def create_benchmark_result(
    result_in: BenchmarkResultCreate,
    db: AsyncSession = Depends(get_db_session),
    _is_super: bool = Depends(is_super_user),
):
    """Create a new benchmark result (Super Users only)."""
    result = BenchmarkResult(**result_in.model_dump())
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result
