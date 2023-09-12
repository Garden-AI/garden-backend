variable "api_cert_arn" {
  description = "The ARN of the ACM certificate"
  type        = string
}

variable "api_cert_domain" {
  description = "The domain name of the ACM certificate"
  type        = string
}

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
