## Repo Layout
I wanted to organize the repo so we'd have a good idea of where new code should go as we build it out, and I took inspiration from a few more mature fastAPI apps (esp. globus compute's) to do so.

here's the Vision:
```
garden-backend-service/
├── README.md             # you are here
├── .env
├── .postgres.env
├── ...
├── src                   # what gets copied into the container
│   ├── api               # any fastapi-specific code lives here
│   │   ├── __init__.py
│   │   ├── dependencies  # fastapi "Dependencies" here
│   │   │   ├── __init__.py
│   │   │   ├── ....
│   │   │   └── auth.py
│   │   ├── schemas       # pydantic models used for request/response validation
│   │   │   ├── __init__.py
│   │   │   ├── ....
│   │   └── routes        # route prefixes should match module names
│   │       ├── __init__.py
│   │       ├── ...
│   │       └── greet.py  # e.g. greet.py has the "/greet" routes
│   │   ...
│   ├── auth              # modules that don't `import fastapi`
│   │   ├── __init__.py
│   │   ├── auth_state.py
│   │   └── globus_auth.py
│   └── models            # sqlalchemy orm models
│       ├── __init__.py
│       ├── base.py
│       └── ....
│   ├── config.py         # settings/reads env vars
│   └── main.py           # inits app/imports routers
├── migrations            # alembic stuff 
│   └── ...
└── tests                 # you guessed it
    ├── __init__.py
    └── test_routes.py
```

## Local development

#### Requirements:
- poetry
- docker
- a .env file in this directory for setting environment variables as wanted/needed.

Our persistent config/environment variables are read from an aws secret at startup. For your local container to have the same config/settings as the live dev deployment, you need to at least set the following in the .env file:

    AWS_ACCESS_KEY_ID=...
    AWS_SECRET_ACCESS_KEY=...
    AWS_SECRET_NAME=garden-backend-env-vars/dev
    GARDEN_ENV=dev
    # see below
    DB_USERNAME="garden_dev"
    DB_PASSWORD="your_password"
    DB_ENDPOINT="dev-db" # hostname of the db container in compose.yaml


where the AWS access key variables correspond to the `garden_lightsail_user_dev` IAM user (which has permission to read the AWS secret). If you provide any additional variables which are also present in the `garden-backend-env-vars/dev` secret, the one you set in the .env file will take priority.

You will also need a .env.postgres file for the postgres container:

    POSTGRES_DB="garden_db_dev"
    POSTGRES_PASSWORD="your_password" #needs to be the same as DB_PASSWORD in .env

POSTGRES variables are used by Docker to configure the database container.

### Testing
Run the API and database containers locally using `docker compose`:

``` sh
docker compose up

# or run in the background
docker compose up -d

# force a rebuild
docker compose up --build
```

Visit http://localhost:5500/docs and behold!

Docker compose maps ./src, ./tests, and ./.env into the container so you can edit files locally
and see the changes immediately reflected in the running container.

Tear down and cleanup the containers:
``` sh
docker compose down
```

If you need to get in and run some database queries manually, connect to the running db container:

``` sh
docker compose exec dev-db psql
```

Similarly, if you need to run commands from the app container:

``` sh
docker compose exec dev-api bash
root@17126a5147f9:/app# pytest    # for example
```

Database data is persisted in a local docker volume defined in `compose.yaml`. If you need a completely fresh
database, remove the volume and restart the containers.
``` sh
docker compose down --volumes
docker compose up 
```

## Deployments
On a push to `dev` or `prod` branches, we run a GitHub action to build and push to the official (and public) `gardenai/garden-service:latest` dockerhub repo, which lightsail then pulls down for the deployment. Logs etc are visible through the [lightsail page](https://lightsail.aws.amazon.com/ls/webapp/home/containers). Note that we don't have any actual "lightsail instances", just a lightsail container service so you'll need to be on the "containers" page to see the logs.
