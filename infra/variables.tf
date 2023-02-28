/*
 * variables.tf
 * Common variables to use in various Terraform files (*.tf)
 */

variable "region" {
  default = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "The id of the team's AWS account"
}

# Tags for the infrastructure
variable "tags" {
  type    = map(string)
  default = {}
}

# The application's name
variable "app" {
  default = "mlflow"
}

# The environment that is being built
variable "environment" {
  default = "prod"
}

# The port the container will listen on, used for load balancer health check
# Best practice is that this value is higher than 1024 so the container processes
# isn't running at root.
variable "container_port" {
  default = 8080
}

# The port the load balancer will listen on
variable "database_port" {
  default = 3306
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

variable "data_subnets" {
  default = "subnet-0392d59bd67242b8b,subnet-016b3eb6829a87ecb"
}

locals {
  namespace      = "${var.app}-${var.environment}"
  target_subnets = split(",", var.private_subnets)
  db_subnets     = split(",", var.private_subnets)
}

variable "artifact_bucket_path" {
  type        = string
  default     = "/"
  description = "The path within the bucket where MLflow will store its artifacts"
}

variable "gunicorn_opts" {
  description = "Additional command line options forwarded to gunicorn processes (https://mlflow.org/docs/latest/cli.html#cmdoption-mlflow-server-gunicorn-opts)"
  type        = string
  default     = ""
}

variable "service_cpu" {
  type        = number
  default     = 2048
  description = "The number of CPU units reserved for the MLflow container"
}

variable "service_memory" {
  type        = number
  default     = 4096
  description = "The amount (in MiB) of memory reserved for the MLflow container"
}

variable "unique_name" {
  type        = string
  default     = "mlflow"
}

variable "database_max_capacity" {
  type        = number
  default     = 4
  description = "The maximum capacity for the Aurora Serverless cluster. Aurora will scale automatically in this range. See: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless.how-it-works.html"
}

variable "database_auto_pause" {
  type        = bool
  default     = true
  description = "Pause Aurora Serverless after a given amount of time with no activity. https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless.how-it-works.html#aurora-serverless.how-it-works.pause-resume"
}

variable "database_seconds_until_auto_pause" {
  type        = number
  default     = 300
  description = "The number of seconds without activity before Aurora Serverless is paused. https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless.how-it-works.html#aurora-serverless.how-it-works.pause-resume"
}

variable "database_skip_final_snapshot" {
  type    = bool
  default = true
}