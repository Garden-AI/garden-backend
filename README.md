# garden-backend

The backend API service for thegardens.ai.

## Repo layout

The API is currently hosted on AWS Lambdas behind AWS API Gateway. Terraform to set up or update the Gateway and Lambdas are in `infra`.

`authorizer` holds the code for an authorizer Lambda that takes a Globus Auth bearer token and emits a policy that grants or denys access to the catchall `/` API resource.

`app` holds the code for our application Lambda, deployed at the `/` route. It assumes the user is logged in and does its own internal routing such that we do not need to deploy new Lambdas for new subroutes.

`garden-backend-service` has the code for the fastAPI app deployed with aws lightsail, the spiritual successor and eventual replacement for `authorizer` and `app`. See also [garden-backend-service/README.md](/garden-backend-service/README.md)


# Branches and deployment
- `.github/workflows` contains our CI/CD config
- `dev` is the default branch (make PRs against `dev`)
- merges to `dev` trigger deployment to our `GardenApp-dev` and `GardenAuthorizer-dev` lambdas
- likewise, merges to `prod` deploy `GardenApp-prod` and `GardenAuthorizer-prod` lambdas
- merges to either also now also deploy the `garden-backend-service` code to their respective lightsail instances 
 
The `dev` branch is the source of truth for development in this repo. `prod` only exists for deployment purposes. Any changes to `prod` that aren't on `dev` will be lost in time, like tears in rain 🤖🌧️. 
