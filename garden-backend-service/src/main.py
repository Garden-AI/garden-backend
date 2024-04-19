from fastapi import FastAPI
from src.api.routes import greet, doi, docker_push_token

app = FastAPI()

app.include_router(greet.router)
app.include_router(doi.router)
app.include_router(docker_push_token.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
