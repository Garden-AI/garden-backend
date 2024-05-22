Alembic migrations for Garden's PostgreSQL database.

# Running `alembic` CLI

You should invoke the `alembic` cli from within a local docker container started with `docker compose`, e.g. 

``` sh
docker compose up
docker compose exec dev-api bash

root@17126a5147f9:/app# alembic do-something
```

# Creating new revisions

Create a new revision by using the following `alembic` command:

```
alembic revision --autogenerate -m "Short message"
```

This will create a file in the `versions` directory, with some helpful defaults.

> The `--autogenerate` flag tells Alembic to generate the migration script by referencing the SQLAlchemy models imported in env.py. Please review the generated script carefully and adjust where necessary.

# Testing migration scripts

Once both containers are up and running, exec into the api container and run:

```
alembic downgrade -1
```

to test the `downgrade` portion of the latest revision, and then run:

```
alembic upgrade head
```

to test the `upgrade` portion. Note that for the live deployments `alembic upgrade head` is run by `./api-entrypoint.sh` just before starting the uvicorn server.
