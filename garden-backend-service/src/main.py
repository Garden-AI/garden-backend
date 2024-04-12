from fastapi import FastAPI
from src.api.routes import greet

app = FastAPI()

app.include_router(greet.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
