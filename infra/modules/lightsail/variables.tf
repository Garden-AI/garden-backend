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
