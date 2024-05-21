from fastapi import APIRouter, Depends
from src.api.dependencies.auth import authed_user
from src.models.user import User

router = APIRouter(prefix="/greet")


@router.get("")
async def greet_authed_user(user: User = Depends(authed_user)):
    name = await user.awaitable_attrs.username
    return {f"Welcome, {name}": "you're looking very... authentic today."}
