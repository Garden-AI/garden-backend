#!/usr/bin/env python3
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_greeting():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "Hello there": "You must be World. You seem familiar, have we met?"
    }
