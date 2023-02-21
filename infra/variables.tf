/*
 * variables.tf
 * Common variables to use in various Terraform files (*.tf)
 */

variable "region" {
  default = "us-east-1"
}

# Tags for the infrastructure
variable "tags" {
  type    = map(string)
  default = {}
}

# The application's name
variable "app" {
  default = "mlflow-dummy"
}

# The environment that is being built
variable "environment" {
  default = "prod"
}

# The port the container will listen on, used for load balancer health check
# Best practice is that this value is higher than 1024 so the container processes
# isn't running at root.
variable "container_port" {
  default = "8080"
}

# The port the load balancer will listen on
variable "lb_port" {
  default = "80"
}

# The load balancer protocol
variable "lb_protocol" {
  default = "TCP"
}

# Network configuration

# The VPC to use for the Fargate cluster
variable "vpc" {
  default = "vpc-02a88a53434cd5aa8"
}

# The private subnets, minimum of 2, that are a part of the VPC(s)
variable "private_subnets" {
  default = "subnet-0392d59bd67242b8b,subnet-016b3eb6829a87ecb"
}

locals {
  namespace      = "${var.app}-${var.environment}"
  target_subnets = split(",", var.private_subnets)
}