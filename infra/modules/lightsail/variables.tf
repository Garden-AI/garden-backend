variable "env" {
  type = string
  description = "Either 'dev' or 'prod'"
}

variable "aws_account_id" {
  description = "The AWS account ID where the resources will be created."
  type        = string
}
