# Garden Backend

This directory includes the Terraform needed to deploy the Garden API infrastructure.
You will likely need to use it if you are doing something like creating a new route or letting the app access a new AWS resource.

## What it does not include

Code deployment.

Deploying changes to the Lambda code is out of Terraform's purview.
If you're making a new API endpoint that has the same auth requirements as an existing one, you probably shouldn't have need to change anything here.

Likewise, building/deploying new docker images for the backend app to the lightsail container service is handled by a github action (see ./github/workflows/deploy-lightsail.yml) rather than terraform.

## What infra is there?
- S3 buckets for storing user notebook contents
- ECR public repository for storing user images
- Lightsail container service for hosting the API
- AWS secrets/etc for the API to read .
  - Due to some lightsail constraints, these mostly live outside of terraform -- see the `garden-backend-env-vars/{dev, prod}` secrets in AWS.
  - Respective deployments are authorized to read their AWS secrets with IAM user credentials (see `garden_lightsail_user_{dev, prod}`in IAM console), which are injected by the GH action at deployment time.

### Subdirectory structure / modules
Almost all resources are configured in dedicated modules under the `modules/` subdirectory. Currently the only exception to this are resources pertaining to the custom `api.thegardens.ai` domain, which live in `prod/main.tf`.

- `modules/secrets_manager`
  - configuration for datacite endpoint/password/prefix secrets
- `modules/s3`
  - configures the s3 buckets for user-published notebook contents
  - allows browsers to read buckets
  - allows api to write buckets
- `modules/lightsail`
  - provisions the lightsail container service(s) to run the deployed container, but does not configure the deployment itself.
  - instead, deploying/running a container on the container service is triggered on push to `dev` or `prod` branches.
    - The baseline configuration is in `modules/lightsail/deployment-config.json` rather than terraform so it can be more easily read by the aws lightsail CLI in the github action.


## Making changes to the existing deployment

Prereqs:
- Have the terraform CLI installed on your machine. (I have used version > 1.3.x)
- Copy the tfvars.example to something like prod.tfvars and get the real values from the AWS console
- Use your preferred method to let Terraform authenticate with AWS

Steps:
- Make your edit to the terraform code.
- From the `dev/` subdirectory:
  - `terraform plan -var-file="dev.tfvars"` and then if you approve, `terraform apply -var-file="dev.tfvars"`
  - Do a sanity check to make sure things are still working in the dev environment
  - If sane, do the same from the `prod/` subdirectory and with `var-file="prod.tfvars"` instead
  - Final sanity check to make sure things are still working, and you're done :)

## Using Terraform

If you're a member of the Garden team with admin AWS access, find the location of the S3 bucket and Dynamo table for doing Terraform updates.
Refer to the secrets manager in us-east-1 for the location/
