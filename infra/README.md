# Garden Backend

This directory includes the Terraform needed to deploy the Garden API infrastructure. 
You will need to use it if you are doing something like creating a new route or letting the app lambda access a new AWS resource.

## What it does not include

Code deployment.

Deploying changes to the Lambda code is out of Terraform's purview. 
If you're making a new API endpoint that has the same auth requirements as an existing one, you probably shouldn't have need to change anything here.

## What infra is there?

- An AWS API Gateway
- An authorizer Lambda that 
- Authorizer Lambda
- App Lambda

## Making changes to the existing deployment

Prereqs:
- Have the terraform CLI installed on your machine. (I have used version > 1.3.x)
- Copy the tfvars.example to something like prod.tfvars and get the real values from the AWS console
- Use your preferred method to let Terraform authenticate with AWS

Steps:
- Make your edit to the terraform code.
- `terraform plan -var-file="{env}.tfvars"` and then if you approve, `terraform apply -var-file="{env}.tfvars"`
- Do a sanity check to make sure things are still working, and you're done :)

## Deploying from scratch

We don't want to use Terraform for our routine code deploys, but also Terraform reasonably refuses to create lambdas without code ot run on them.
So if you're deploying from scratch, you will need to place an `authorizer.zip` and `app.zip` in the infra directory.
You can follow the shell commands in the GH Action yaml to see how to zip it up properly, but also you could just use dummy files and it would be fine.

## Using Terraform

If you're a member of the Garden team with admin AWS access, find the location of the S3 bucket and Dynamo table for doing Terraform updates. 
Refer to the secrets manager in us-east-1 for the location/

## Gotchas

The concept of an AWS API Gateway "deployment" is really weird and doesn't play too nicely with Terraform. 
The deployment should only change if you add a new Lambda to the gateway or change the gateway routing. 
Just NB that if you've applied a change at that level and things are acting weird, it's a decent bet to look at the API Gateway stage's deployments tab and make sure it's pointed to the right one.