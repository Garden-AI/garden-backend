
variable "garden_app_invoke_arn" {
  description = "The invoke ARN of the GardenApp Lambda function"
  type        = string
}

variable "garden_app_function_name" {
  description = "The function name of the GardenApp Lambda function"
  type        = string
}

variable "garden_authorizer_invoke_arn" {
  description = "The invoke ARN of the GardenAuthorizer Lambda function"
  type        = string
}

variable "garden_authorizer_function_name" {
  description = "The function name of the GardenAuthorizer Lambda function"
  type        = string
}

variable "env" {
  type = string
  description = "Either 'dev' or 'prod'"
}
