output "db_endpoint" {
  description = "The endpoint of the RDS instance."
  value       = aws_db_instance.garden_db.endpoint
}

output "db_name" {
  description = "The name of the database."
  value       = aws_db_instance.garden_db.db_name
}

output "db_security_group_id" {
  description = "The security group ID for the RDS instance."
  value       = aws_security_group.garden_db_sg.id
}

output "bastion_public_ip" {
  description = "The public IP address of the bastion EC2 instance."
  value       = aws_instance.rds_bastion.public_ip
}
