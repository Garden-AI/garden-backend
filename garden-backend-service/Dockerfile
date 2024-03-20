FROM python:3.11

WORKDIR /app/

# paraphrased from: https://github.com/tiangolo/full-stack-fastapi-template/blob/master/backend/Dockerfile
# Install Poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

# Copy poetry files
COPY ./pyproject.toml ./poetry.lock* /app/

# Allow installing dev dependencies (see ./run-dev-server.sh)
ARG INSTALL_DEV=false
RUN bash -c "if [ $INSTALL_DEV == 'true' ] ; then poetry install --no-root --with=develop; else poetry install --no-root --only main ; fi"

COPY ./src /app/src

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
