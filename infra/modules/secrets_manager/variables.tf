variable "aws_account_id" {
  description = "The AWS account ID where the resources will be created."
  type        = string
}

variable "env" {
  description = "The environment (dev or prod) where the resources will be created."
  type        = string
}

variable "lightsail_iam_user_name" {
  description = "The IAM user name for the lightsail deployment"
  type        = string
}

variable "tags" {
  type = map(string)
  default = {
    Project = "Garden"
  }
}
