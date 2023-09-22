# Garden Backend

This directory includes the Terraform needed to deploy the Garden API infrastructure. 
You will need to use it if you are doing something like creating a new route or letting the app lambda access a new AWS resource.

## What it does not include

Code deployment.

Deploying changes to the Lambda code is out of Terraform's purview. 
If you're making a new API endpoint that has the same auth requirements as an existing one, you probably shouldn't have need to change anything here.

## What infra is there?

- An AWS API Gateway
- Authorizer Lambda
- App Lambda
- S3 buckets for storing model binaries

### Subdirectory structure / modules
Almost all resources are configured in dedicated modules under the `modules/` subdirectory. Currently the only exception to this are resources pertaining to the custom `api.thegardens.ai` domain, which live in `prod/main.tf`. 

- `modules/api_gateway`
  - contains every `aws_api_gateway_*` resource
  - requires input variables to plug into the app/auth lambdas
  - provisions totally distinct resources based on `env` input variable 
- `modules/lambda`
  - resources for both the GardenApp and GardenAuthorizer lambdas
  - also configures relevant IAM resources 
  - distinct resources based on `env` input variable 
- `modules/secrets_manager`
  - configuration for datacite endpoint/password/prefix secrets
  - IAM resources are distinct based on `var.env`, but the actual datacite secrets are still the same (for now) 
- `modules/s3`
  - configures the s3 buckets for model binaries for both dev and prod together 
  - also configures the `"s3_full_access"` IAM policy if we want to change that based on env, but currently keeps it the same for both. 

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

## Deploying from scratch

We don't want to use Terraform for our routine code deploys, but also Terraform reasonably refuses to create lambdas without code ot run on them.
So if you're deploying from scratch, you will need to place an `authorizer.zip` and `app.zip` in the `infra/dev` or `infra/prod` directory.
You can follow the shell commands in the GH Action yaml to see how to zip it up properly, but also you could just use dummy files and it would be fine.

## Using Terraform

If you're a member of the Garden team with admin AWS access, find the location of the S3 bucket and Dynamo table for doing Terraform updates. 
Refer to the secrets manager in us-east-1 for the location/

## Gotchas

The concept of an AWS API Gateway "deployment" is really weird and doesn't play too nicely with Terraform. 
The deployment should only change if you add a new Lambda to the gateway or change the gateway routing. 
Just NB that if you've applied a change at that level and things are acting weird, it's a decent bet to look at the API Gateway stage's deployments tab and make sure it's pointed to the right one.
