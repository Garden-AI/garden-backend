# garden-backend

The backend API service for thegardens.ai.

## Repo layout

The API is currently hosted on AWS Lambdas behind AWS API Gateway. Terraform to set up or update the Gateway and Lambdas are in `infra`.

`authorizer` holds the code for an authorizer Lambda that takes a Globus Auth bearer token and emits a policy that grants or denys access to the catchall `/` API resource.

`app` holds the code for our application Lambda, deployed at the `/` route. It assumes the user is logged in and does its own internal routing such that we do not need to deploy new Lambdas for new subroutes.

`.github/workflows` contains our CI/CD config. It deploys the Lambdas on every push to `main`.