from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.database import get_db_session

router = APIRouter(prefix="/hello-database")


@router.get("")
async def hello_postgres(session: AsyncSession = Depends(get_db_session)):
    # Execute a query to return the current time
    result = await session.execute(select(func.now()))
    current_time = result.scalar()
    return {
        "Hello, postgres": "Do you have the time?",
        "the time is": f"{current_time}",
    }
