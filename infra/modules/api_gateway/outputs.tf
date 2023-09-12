output "api_execution_arn" {
  description = "The ARN prefix to be used in invoking the API Gateway. Use it to set permissions for Lambda functions."
  value       = aws_api_gateway_rest_api.garden_api.execution_arn
}

output "api_domain_name" {
  description = "The custom domain name associated with the API Gateway."
  value       = aws_api_gateway_domain_name.api_domain_name.domain_name
}

output "api_cloudfront_domain_name" {
  description = "The CloudFront domain name automatically generated for this API Gateway."
  value       = aws_api_gateway_domain_name.api_domain_name.cloudfront_domain_name
}

output "api_cloudfront_zone_id" {
  description = "The Zone ID associated with the CloudFront distribution backing the API Gateway."
  value       = aws_api_gateway_domain_name.api_domain_name.cloudfront_zone_id
}

output "stage_invoke_url" {
  description = "The URL to invoke the API Gateway."
  value       = aws_api_gateway_stage.garden_api.invoke_url
}
