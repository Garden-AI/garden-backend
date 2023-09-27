variable "aws_account_id" {
  description = "The AWS account ID where the resources will be created."
  type        = string
}

variable "env" {
  description = "The environment (dev or prod) where the resources will be created."
  type        = string
}

variable "lambda_exec_role_name" {
  description = "The IAM role name that will be assumed by the Lambda functions."
  type        = string
}
