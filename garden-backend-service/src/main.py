from fastapi import FastAPI
from src.api.routes import (
    docker_push_token,
    doi,
    entrypoints,
    garden_search_record,
    gardens,
    greet,
    hello_database,
    notebook,
)

app = FastAPI()

app.include_router(greet.router)
app.include_router(doi.router)
app.include_router(docker_push_token.router)
app.include_router(notebook.router)
app.include_router(garden_search_record.router)
app.include_router(hello_database.router)
app.include_router(entrypoints.router)
app.include_router(gardens.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
