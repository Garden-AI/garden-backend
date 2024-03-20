from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def greet_world():
    return {"Hello there": "You must be World. You seem familiar, have we met?"}
