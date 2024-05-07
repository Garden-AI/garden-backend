from fastapi import FastAPI

from src.api.routes import docker_push_token, doi, garden_search_record, greet, notebook, hello_database

app = FastAPI()

app.include_router(greet.router)
app.include_router(doi.router)
app.include_router(docker_push_token.router)
app.include_router(notebook.router)
app.include_router(garden_search_record.router)
app.include_router(hello_database.router)


@app.get("/")
async def greet_world():
    return {"Hello there": "You must be World"}
