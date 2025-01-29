#!/bin/bash
set -ex

# Run Alembic migrations
uv run alembic upgrade head

# Start the Uvicorn server
exec uv run uvicorn src.main:app --host 0.0.0.0 --port 80 --workers 5
