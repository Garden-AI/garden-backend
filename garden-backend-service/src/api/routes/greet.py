from fastapi import APIRouter, Depends
from src.api.dependencies.auth import authenticated, AuthenticationState

router = APIRouter(prefix="/greet")


@router.get("")
async def greet_authed_user(auth: AuthenticationState = Depends(authenticated)):
    name = auth.username
    return {f"Welcome, {name}": "you're looking very... authentic today."}
