from fastapi import FastAPI
from src.api.routes import greetings

app = FastAPI()

app.include_router(greetings.router, prefix="/greetings")


@app.get("/")
def greet_world():
    return {"Hello there": "You must be World. You seem familiar, have we met?"}
