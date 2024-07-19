output "db_username" {
  value       = jsondecode(data.aws_secretsmanager_secret_version.current.secret_string)["DB_USERNAME"]
  description = "Database username retrieved from Secrets Manager."
}

output "db_password" {
  value       = jsondecode(data.aws_secretsmanager_secret_version.current.secret_string)["DB_PASSWORD"]
  description = "Database password retrieved from Secrets Manager."
  sensitive   = true
}
