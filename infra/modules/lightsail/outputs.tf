output "container_service_name" {
  description = "The name of the Lightsail container service."
  value       = aws_lightsail_container_service.garden_service.id
}

output "container_service_state" {
  description = "The current state of the service."
  value       = aws_lightsail_container_service.garden_service.state
}

output "container_service_url" {
  description = "The publicly accessible URL of the service."
  value       = aws_lightsail_container_service.garden_service.url
}

output "container_service_domain" {
  description = "The domain name of the container service deployment"
  value       = trimsuffix(replace(aws_lightsail_container_service.garden_service.url, "https://", ""), "/")
}

output "lightsail_container_service_hosted_zone_id" {
  description = "The (fixed) hosted zone ID for lightsail container services in us-east-1"
  value       = "Z06246771KYU0IRHI74W4"
  # see: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-route-53-alias-record-for-container-service.html#route-53-container-service-hosted-zone-ids
}

output "lightsail_iam_user_name" {
  value = aws_iam_user.lightsail_user.name
}
