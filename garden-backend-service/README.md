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
- a .env file in this directory setting API_CLIENT_ID and API_CLIENT_SECRET appropriately for auth purposes 
    - values from `garden/globus_api` secret in aws
    - you can set the env vars in the container another way if you want, especially if you're not using `./run-dev-server.sh` to run the container 

### Testing
Running `./run-dev-server.sh` will spin up the app at http://localhost:5500 in a container almost exactly like the one used for deployment, with the following tweaks:

- mounts ./src as shared volume (instead of COPY) so local changes propagate into the container
- also mounts ./.env file so the app can read e.g. API_CLIENT_SECRET vars. The .env file does not exist in the (public) image we deploy from.
- runs uvicorn with --reload so changes you make in ./src get picked up immediately

In addition to curl, postman etc you can also visit http://localhost:5500/docs in a browser for interactive docs that let you exercise specific endpoints.

Unit tests live in `./tests/` and are run by github actions on PRs, or can be run locally w/ `poetry run pytest`

## Deployments 
On a push to `dev` or `prod` branches, we run a GitHub action to build and push to the official (and public) `gardenai/garden-service:latest` dockerhub repo, which lightsail then pulls down for the deployment. Logs etc are visible through the [lightsail page](https://lightsail.aws.amazon.com/ls/webapp/home/containers). Note that we don't have any actual "lightsail instances", just a lightsail container service so you'll need to be on the "containers" page.

