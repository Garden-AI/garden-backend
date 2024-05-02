variable "env" {
  type = string
  description = "Either 'dev' or 'prod'"
}

variable "aws_account_id" {
  description = "The AWS account ID where the resources will be created."
  type        = string
}

variable "ecr_access_policy_arn" {
  description = "The ARN for the ECR access policy to attach."
  type        = string
}

variable "s3_access_policy_arn" {
  description = "The ARN for the S3 access policy to attach."
  type        = string
}

variable "lightsail_certificate_name" {
  description = "The name of the lightsail certificate for the custom domain, e.g. 'api-dev-certificate'."
  type = string
}

variable "lightsail_certificate_domain_name" {
  # note: may need to manually add record in route53 if corresponding lightsail cert doesn't already exist
  description = "The custom domain name for the deployment, e.g. 'api-dev.thegardens.ai'"
  type = string
}
