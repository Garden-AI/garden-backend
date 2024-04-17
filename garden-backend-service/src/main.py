from fastapi import FastAPI
from src.api.routes import greet, doi

app = FastAPI()

app.include_router(greet.router)
app.include_router(doi.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
