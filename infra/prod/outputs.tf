# Output value definitions

output "function_name" {
  description = "Name of the Lambda function."

  value = module.lambda.garden_app_function_name
}

output "base_url" {
  description = "Base URL for API Gateway stage."

  value = module.api_gateway.stage_invoke_url
}
