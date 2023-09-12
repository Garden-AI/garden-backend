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

# variable "env" {
#   type = string
#   description = "Either 'dev' or 'prod'"
# }
