from fastapi import FastAPI
from src.api.routes import greetings

app = FastAPI()

app.include_router(greetings.router)
