#!/bin/bash

IMAGE_NAME="garden-service-dev"

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

# Run the normal Docker container with the following options:
# - mount ./app as shared volume (instead of COPY) so local changes propagate into the container
# - run uvicorn with --reload so those changes get picked up
echo "Running the Docker container with live reload at http://localhost:5500 ..."
docker run -p 5500:80 \
    -v $(pwd)/app:/app/app \
    --name garden-service-dev-container \
    --rm \
    $IMAGE_NAME \
    uvicorn app.main:app --host 0.0.0.0 --port 80 --reload
