terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
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
  source = "../modules/secrets_manager"

  env                     = var.env
  aws_account_id          = var.aws_account_id
  lightsail_iam_user_name = module.lightsail.lightsail_iam_user_name
}

module "s3" {
  source = "../modules/s3"

  env = var.env
}

module "ecr" {
  source = "../modules/ecr"

  env = var.env
}

module "lightsail" {
  source                            = "../modules/lightsail"
  aws_account_id                    = var.aws_account_id
  env                               = var.env
  ecr_access_policy_arn             = module.ecr.ecr_backend_write_policy_arn
  s3_access_policy_arn              = module.s3.full_access_arn
  lightsail_certificate_name        = "api-dev-certificate"
  lightsail_certificate_domain_name = data.aws_acm_certificate.api_cert.domain
}

module "rds" {
  source = "../modules/rds"

  env         = var.env
  db_username = module.secrets_manager.db_username
  db_password = module.secrets_manager.db_password
}

/* point api-dev.thegardens.ai to the lightsail deployment */

data "aws_route53_zone" "hosted_zone" {
  name = var.root_domain_name
}

data "aws_acm_certificate" "api_cert" {
  domain = "${var.subdomain_prefix}.${var.root_domain_name}"
}

resource "aws_route53_record" "api_record" {
  name    = data.aws_acm_certificate.api_cert.domain
  type    = "A"
  zone_id = data.aws_route53_zone.hosted_zone.id

  alias {
    evaluate_target_health = true
    name                   = module.lightsail.container_service_domain
    zone_id                = module.lightsail.lightsail_container_service_hosted_zone_id
  }
}
