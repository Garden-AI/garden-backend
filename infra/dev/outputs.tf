# Output value definitions

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

output "api_endpoint_url" {
  description = "The full URL for the API endpoint"
  value = "https://${var.subdomain_prefix}.${var.root_domain_name}"
}
