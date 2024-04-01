#!/bin/bash

IMAGE_NAME="garden-service:dev"

# Build the Docker image with dev dependencies
echo "Building Docker image with development dependencies..."
docker build --build-arg INSTALL_DEV=true -t $IMAGE_NAME .

# Check if the build was successful
if [ $? -eq 0 ]; then
    echo "Successfully built the Docker image."
else
    echo "Failed to build the Docker image. Exiting..."
    exit 1
fi

# Run like the deployment Docker container with the following tweaks:
# - mount ./src as shared volume (instead of COPY) so local changes propagate into the container
# - also mount ./tests so you can run pytest
# - also mount ./.env file (if it exists - not checked into vc) so app can read e.g. API_CLIENT_SECRET vars
# - run uvicorn with --reload so those changes get picked up
echo "Running the Docker container with live reload at http://localhost:5500 ..."
docker run -p 5500:80 \
    -v $(pwd)/src:/app/src \
    -v $(pwd)/tests:/app/tests \
    -v $(pwd)/.env:/app/.env \
    --name garden-service-dev-container \
    --rm \
    $IMAGE_NAME \
    uvicorn src.main:app --host 0.0.0.0 --port 80 --reload
