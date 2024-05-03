# garden-backend

The backend API service for thegardens.ai.

## Repo layout
The API is currently hosted on an AWS lightsail container service.
`infra` contains the terraform modules to provision both dev and prod instances of the necessary AWS resources. See also [infra/README.md](/infra/README.md).

`garden-backend-service` is the python source code for the fastAPI app deployed with lightsail. See also [garden-backend-service/README.md](/garden-backend-service/README.md).

`.github/workflows` contains our CI/CD config used to actually test and deploy the app. 

Note that there are no GH actions to actually apply changes to the terraform code in `infra`. Real changes to infra need to be made explicitly by someone with the necessary permissions to `terraform apply` them. You might need to `terraform apply` to dev before a PR has been approved, but don't apply changes to prod until they're approved. 

# Branches and deployment
- `dev` is the default branch (make PRs against `dev`)
- merges to `dev` trigger (re-)deployment to our `garden-service-dev` lightsail container service.
- likewise, merges to `prod` deploy to `garden-service-prod` on lightsail.
 
The `dev` branch is the source of truth for development in this repo. `prod` only exists for deployment purposes. Any changes to `prod` that aren't on `dev` will be lost in time, like tears in rain 🤖🌧️. 
