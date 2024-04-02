from fastapi import APIRouter, Depends
from src.api.dependencies.auth import authenticated, AuthenticationState

router = APIRouter(prefix="/greet")


@router.get("/")
async def greet_world(name: str):
    return {"Hello there": "You must be World. You seem familiar, have we met?"}


@router.get("/{name}")
async def greet_name(name: str):
    return {f"Hello, {name}": "Say hi to world for me."}


@router.get("/vip")
async def greet_vip(auth: AuthenticationState = Depends(authenticated)):
    name = auth.username
    return {f"Welcome, {name}": "you're looking very... authentic this evening."}
