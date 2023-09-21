output "api_execution_arn" {
  description = "The ARN prefix to be used in invoking the API Gateway. Use it to set permissions for Lambda functions."
  value       = aws_api_gateway_rest_api.garden_api.execution_arn
}

output "stage_invoke_url" {
  description = "The URL to invoke the API Gateway."
  value       = aws_api_gateway_stage.garden_api.invoke_url
}
