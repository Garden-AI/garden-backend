from fastapi import FastAPI
from src.api.routes import greetings

app = FastAPI()

app.include_router(greetings.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
