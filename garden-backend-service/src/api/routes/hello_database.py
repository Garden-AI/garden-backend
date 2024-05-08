from fastapi import APIRouter, Depends

from src.api.dependencies.database import get_db_session, SessionLocal
from sqlalchemy import func, select

router = APIRouter(prefix="/hello-database")


@router.get("")
def hello_postgres(session: SessionLocal = Depends(get_db_session)):
    # Execute a query to return the current time
    result = session.execute(select(func.now()))
    current_time = result.scalar()
    return {"Hello, postgres": "Do you have the time?", "the time is": f"{current_time}"}
