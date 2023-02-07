terraform {

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.4"
    }
  }

  backend "s3" {
    bucket         = "garden-backend-terraform-state"
    key            = "mlflow/s3/terraform.tfstate"
    region         = "us-east-1"

    dynamodb_table = "garden-mlflow-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

