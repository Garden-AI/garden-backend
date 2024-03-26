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
