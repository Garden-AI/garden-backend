## Repo Layout
I wanted to organize the repo so we'd have a good idea of where new code should go as we build it out, and I took inspiration from a few more mature fastAPI apps (esp. globus compute's) to do so.

here's the Vision:
```
garden-backend-service/
├── README.md               # you are here
├── .env
├── .postgres.env
├── ...
├── src                     # what gets copied into the container
│   ├── api                 # any fastapi-specific code lives here
│   │   ├── __init__.py
│   │   ├── dependencies    # fastapi "Dependencies" here
│   │   │   ├── __init__.py
│   │   │   ├── ....
│   │   │   └── auth.py
│   │   ├── schemas         # pydantic models used for request/response validation
│   │   │   ├── __init__.py
│   │   │   ├── ....
│   │   └── routes          # route prefixes should match module names
│   │       ├── __init__.py
│   │       ├── gardens.py  # e.g. gardens.py has the "/gardens" routes
│   │       └── ...
│   │   ...
│   ├── auth                # modules that don't `import fastapi`
│   │   ├── __init__.py
│   │   ├── auth_state.py
│   │   └── globus_auth.py
│   └── models              # sqlalchemy orm models
│       ├── __init__.py
│       ├── base.py
│       └── ....
│   ├── config.py           # settings/reads env vars
│   └── main.py             # inits app/imports routers
├── migrations              # alembic stuff
│   └── ...
└── tests                   # you guessed it
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


## Connect pgadmin to RDS instances

**Note:** You will need to follow this process for each instance (dev and prod). You can
use the same key pair for both instances.

### **Create ssh key pair**

Either through the AWS console or on the command line create an RSA
keypair.

- **Option 1 AWS Console**

  Login to AWS and navigate to the EC2 Console. On the left nav panel
  under network and security select *Key Pairs*.

  Click *Create key pair*.

  Select "RSA" for the key pair type and select ".pem" for the format.

  Create the key pair by clicking *Create key pair* at the bottom of
  the page. Make sure to download the generated key pair as this is
  the only opportunity you have to save it. If you lose it you will
  need to create a new one.

- **Option 2 local command line**

  Use `ssh-keygen` to generate a key pair locally:

  ```sh
  ssh-keygen -m PEM -t rsa -b 4096
  ```

### **Add public key to EC2 instance**

Login to AWS and go to the EC2 console. Click *Instances* on the
left nav panel.

Select the instance you want to connect to by clicking the
checkbox next to the instance name. Then, click *Connect* and select
the *EC2 Instance Connect* tab. For the connection type select
*Connect using EC2 Instance Connect* and leave the username as the
default `ubuntu`.

Click *Connect* at the bottom of the page and a terminal will open
connected to the EC2 instance in the ec2-user's home directory.

Add the public key of your new key pair to the file
`~/.ssh/authorized_keys`.

``` sh
echo "<public-key>" >> .ssh/authorized_keys
```
You now have the ability to login to the instance with ssh using the
private key from your key pair.

``` sh
ssh -i <path-to-private-key> ubuntu@<hostname-or-ip-of-instance>
```

### **Configure pgadmin**

With the pgadmin container running via `docker compose`, login to
pgadmin at [localhost:8080](http://localhost:8080/).

Click *Add New Server*.

Set the name of the server to something meaningful like
'garden_db_dev', then select the *Connection* tab.

For the *Host name/address*, *username* and *password* fields, check the `garden-backend-env-vars/{dev, prod}`AWS secret and copy the appropriate values (`DB_ENDPOINT`/ `DB_USERNAME`/`DB_PASSWORD`, respectively).

Keep the *port* and *maintenance database* set with their default values.

Move to the *SSH Tunnel* tab of the server configuration and toggle
*Use SSH tunneling* on.

*Tunnel host* should be the public hostname or IP of the EC2 instance.
*Tunnel port* should be `22`
*Username* should be `ubuntu`
For *Authentication*, select *Identity file*

The *Identity file* should be the private key from your key
pair. Click the folder icon and select the private key file. Since
pgadmin is running in a container you will need to upload your private
key file before you can select it here. Click the three dots in the
upper right side of the file browser and select upload. Add the
private key file from you key pair. Once the file is uploaded to the
container, you can select it.

Click *Save* and if everything goes well pgadmin should connect to the
RDS instance using the EC2 instance as an ssh tunnel.
