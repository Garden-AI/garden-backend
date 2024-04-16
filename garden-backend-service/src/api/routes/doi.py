from fastapi import APIRouter, Depends
from src.api.dependencies.auth import authenticated, AuthenticationState
from src.config import settings

router = APIRouter(prefix="/doi")


@router.put("/")
async def put_datacite(auth: AuthenticationState = Depends(authenticated)):
    name = auth.username
    pass


@router.post("/")
async def post_datacite(auth: AuthenticationState = Depends(authenticated)):
    name = auth.username
    pass
