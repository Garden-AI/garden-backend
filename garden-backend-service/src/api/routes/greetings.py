#!/usr/bin/env python3
from fastapi import APIRouter, Depends
from src.api.dependencies.auth import authenticated, AuthenticationState

router = APIRouter()


@router.get("/{name}")
async def greet_name(name: str):
    return {f"Hello, {name}": "Say hi to world for me."}


@router.get("/")
async def greet_vip(auth: AuthenticationState = Depends(authenticated)):
    name = auth.username
    return {f"Welcome, {name}": "you're looking very... authentic this evening."}
