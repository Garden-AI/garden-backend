/*
 * variables.tf
 * Common variables to use in various Terraform files (*.tf)
 */

variable "aws_account_id" {
  type        = string
  description = "The id of the team's AWS account"
}

# Tags for the infrastructure
variable "tags" {
  type    = map(string)
  default = {}
}

variable "env" {
  type        = string
  description = "Either 'dev' or 'prod'"
  default     = "dev"
}

variable "subdomain_prefix" {
  type        = string
  description = "Prefix for the subdomain (e.g. 'api-dev') used to create a fully qualified domain name for the deployment."
  default     = "api-dev"
}

variable "root_domain_name" {
  type        = string
  description = "Root domain (e.g. 'thegardens.ai') associated with the AWS Route 53 hosted zone where the subdomain will be configured."
  default     = "thegardens.ai"
}
