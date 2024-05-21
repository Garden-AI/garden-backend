#!/bin/bash
set -ex

# Run Alembic migrations
poetry run alembic upgrade head

# Start the Uvicorn server
exec uvicorn src.main:app --host 0.0.0.0 --port 80
