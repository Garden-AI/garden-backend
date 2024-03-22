terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0.0"
    }
  }
  required_version = "~> 1.3.0"
  backend "s3" {
    bucket = "garden-backend-terraform-state"
    key    = "garden-backend/dev/terraform.tfstate"
    region = "us-east-1"

    dynamodb_table = "garden-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}


module "secrets_manager" {
  source               = "../modules/secrets_manager"

  env                  = var.env
  aws_account_id       = var.aws_account_id
  lambda_exec_role_name = module.lambda.lambda_exec_role_name
}

module "api_gateway" {
  source                          = "../modules/api_gateway"

  env                             = var.env
  garden_app_invoke_arn           = module.lambda.garden_app_invoke_arn
  garden_app_function_name        = module.lambda.garden_app_function_name
  garden_authorizer_invoke_arn    = module.lambda.garden_authorizer_invoke_arn
  garden_authorizer_function_name = module.lambda.garden_authorizer_function_name
}

module "lambda" {
  source = "../modules/lambda"

  env = var.env
  api_gateway_execution_arn = module.api_gateway.api_execution_arn
  s3_access_policy_arn = module.s3.full_access_arn
  ecr_access_policy_arn = module.ecr.ecr_backend_write_policy_arn
}

module "s3" {
  source = "../modules/s3"
  
  env    = var.env
}

module "ecr" {
  source = "../modules/ecr"

  env    = var.env
}

module "lightsail" {
  source = "../modules/lightsail"
  env = var.env
}
