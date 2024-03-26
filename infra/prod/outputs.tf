# Output value definitions

output "function_name" {
  description = "Name of the Lambda function."

  value = module.lambda.garden_app_function_name
}

output "base_url" {
  description = "Base URL for API Gateway stage."

  value = module.api_gateway.stage_invoke_url
}

output "container_service_name" {
  description = "The name of the Lightsail container service."
  value       = module.lightsail.container_service_name
}

output "container_service_state" {
  description = "The current state of the service."
  value       = module.lightsail.container_service_state
}

output "container_service_url" {
  description = "The publicly accessible URL of the service."
  value       = module.lightsail.container_service_url
}
