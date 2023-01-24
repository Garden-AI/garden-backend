# Output value definitions

output "function_name" {
  description = "Name of the Lambda function."

  value = aws_lambda_function.garden_app.function_name
}

output "base_url" {
  description = "Base URL for API Gateway stage."

  value = aws_api_gateway_stage.garden_api.invoke_url
}