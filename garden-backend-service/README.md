## Repo Layout
I wanted to organize the repo so we'd have a good idea of where new code should go as we build it out, and I took inspiration from a few more mature fastAPI apps (esp. globus compute's) to do so.

here's the Vision:
``` 
garden-backend-service/
├── ...
├── README.md # you are here
├── src       # what gets copied into the container 
│   ├── api     # any fastapi-specific code lives here
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
│   ├── config.py         # settings/reads env vars
│   └── main.py           # inits app/imports routers 
└── tests       # you guessed it
    ├── __init__.py
    └── test_routes.py
```

## Local development

#### Requirements:
- poetry 
- docker
- postgres
  - see "Local PostgreSQL setup" below
- a .env file in this directory for setting environment variables as wanted/needed. 

Our persistent config/environment variables are read from an aws secret at startup. For your local container to have the same config/settings as the live dev deployment, you need to at least set the following in the .env file:

    AWS_ACCESS_KEY_ID=... 
    AWS_SECRET_ACCESS_KEY=...
    AWS_SECRET_NAME=garden-backend-env-vars/dev
    GARDEN_ENV=dev
    SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://garden_dev:<your_password>@host.docker.internal/garden_ai 
    
where the AWS access key variables correspond to the `garden_lightsail_user_dev` IAM user (which has permission to read the AWS secret). If you provide any additional variables which are also present in the `garden-backend-env-vars/dev` secret, the one you set in the .env file will take priority. 

### Local PostgreSQL setup 
You'll need postgres installed locally and configured to allow connections from the docker container. 

0. install/start postgres server
  - on mac, [Postgres.app](https://postgresapp.com/downloads.html) is probably the easiest option 
1. create a `garden_ai` database and `garden_dev` user with the postgres CLI:

``` sql
$ psql postgres
psql (16.2 (Homebrew))
Type "help" for help.

postgres=# CREATE DATABASE garden_ai;
CREATE DATABASE
postgres=# CREATE USER garden_dev WITH ENCRYPTED PASSWORD 'your_password';
CREATE ROLE
postgres=# GRANT ALL PRIVILEGES ON DATABASE garden_ai TO garden_dev;
GRANT
```

2. edit your `postgresql.conf` to set `listen_addresses`:
  - the location of this file depends on how you installed postgres; you can find it in Postgress.app via "server settings" or at `/opt/homebrew/var/postgresql@16/postgresql.conf` if installed with homebrew.
  - uncomment the line `listen_addresses = 'localhost'` and set it to `'*'` to allow connections from any IP. 
    - Alternatively, you can set it to `'localhost,172.17.0.1'` to allow connections only from localhost and docker containers (where 172.17.0.1 is the docker subnet gateway -- run `docker network inspect bridge`to double check).
3. edit `pg_hba.conf` (same dir as `postgresql.conf`) to add a connection rule for docker containers:
  - paste the following line at the bottom (assuming default docker subnet 172.17.0.0/16):

```
host    all             all             172.17.0.0/16           md5
```

4. Add a `SQLALCHEMY_DATABASE_URL` to your `.env` file:

``` sh
# garden-backend/garden-backend-service/.env
...
SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://garden_dev:<your_password>@host.docker.internal/garden_ai 
```

### Testing
Running `./run-dev-server.sh` will spin up the app at http://localhost:5500 in a container almost exactly like the one used for deployment, with the following tweaks:

- mounts ./src as shared volume (instead of COPY) so local changes propagate into the container
- also mounts ./.env file so the app can read e.g. API_CLIENT_SECRET vars. The .env file does not exist in the (public) image we deploy from.
  - your .env file should also set the `SQLALCHEMY_DATABASE_URL` var to point at your local postgres (see above)
- runs uvicorn with --reload so changes you make in ./src get picked up immediately

In addition to curl, postman etc you can also visit http://localhost:5500/docs in a browser for interactive docs that let you exercise specific endpoints.

Unit tests live in `./tests/` and are run by github actions on PRs, or can be run locally w/ `poetry run pytest`

## Deployments 
On a push to `dev` or `prod` branches, we run a GitHub action to build and push to the official (and public) `gardenai/garden-service:latest` dockerhub repo, which lightsail then pulls down for the deployment. Logs etc are visible through the [lightsail page](https://lightsail.aws.amazon.com/ls/webapp/home/containers). Note that we don't have any actual "lightsail instances", just a lightsail container service so you'll need to be on the "containers" page.

