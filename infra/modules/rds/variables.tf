variable "env" {
  description = "Environment (e.g., 'prod', 'dev')."
  type        = string
}

variable "db_username" {
  description = "Username for the database administrator."
  type        = string
}

variable "db_password" {
  description = "Password for the database administrator."
  type        = string
  sensitive   = true
}

## optional variables ##

variable "postgres_version" {
  description = "The version of PostgreSQL."
  type        = string
  default     = "16"
}

variable "instance_class" {
  description = "The instance type of the RDS instance."
  type        = string
  default     = "db.t3.micro"
}


variable "allocated_storage" {
  description = "The allocated storage size for the RDS instance (in GB)."
  type        = number
  default     = 10
}

variable "max_allocated_storage" {
  description = "The maximum allocated storage size for the RDS instance (in GB)."
  type        = number
  default     = 50
}

# defaults copied from default VPC console after enabling VPC peering in lightsail
variable "lightsail_cidr" {
  description = "CIDR block for the Lightsail container service."
  type        = string
  default     = "172.26.0.0/16"
}

variable "lightsail_cidr_ipv6" {
  description = "IPv6 CIDR block for the Lightsail container service."
  type        = string
  default     = "2600:1f18:cb3:ff00::/56"
}
