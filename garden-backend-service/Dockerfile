FROM python:3.12
WORKDIR /app

# Install uv binary directly from the latest official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
# copy instead of symlink since we don't include uv's cache in the final image
ENV UV_LINK_MODE=copy

# Install dependencies using uv with:
# - A cached uv package directory (type=cache)
# - Temporary access to requirements files (type=bind)
# see: https://docs.astral.sh/uv/guides/integration/docker/#caching
ARG INSTALL_DEV=false
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  if [ "$INSTALL_DEV" = "true" ] ; then \
  uv sync --frozen --no-install-project --group develop ; \
  else \
  uv sync --frozen --no-install-project --no-group develop; \
  fi

# Copy code to /app/
COPY pyproject.toml uv.lock alembic.ini api-entrypoint.sh /app/
COPY migrations /app/migrations
COPY src /app/src
RUN chmod +x /app/api-entrypoint.sh

# finally install the project itself in its own layer
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen

EXPOSE 80

ENTRYPOINT ["/app/api-entrypoint.sh"]
