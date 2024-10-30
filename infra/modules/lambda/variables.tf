variable "env" {
  description = "The environment for the deployment. (dev, prod)"
  type        = string
}

variable "server_name" {
  description = "The name of the Lightsail container service"
  type        = string
}

variable "aws_account_id" {
  description = "The AWS account ID where the resources will be created."
  type        = string
}
