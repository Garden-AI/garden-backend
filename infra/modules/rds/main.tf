data "aws_vpc" "default" {
  default = true
}

# security group for rds in default vpc
# allowing connections from lightsail container(s)
resource "aws_security_group" "garden_db_sg" {
  name        = "garden-db-sg-${var.env}"
  description = "Allow Lightsail resources to access RDS instance"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port = 5432
    to_port   = 5432
    protocol  = "tcp"
    # allow connections from lightsail CIDR blocks
    cidr_blocks      = [var.lightsail_cidr]
    ipv6_cidr_blocks = [var.lightsail_cidr_ipv6]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.env
  }

  lifecycle {
    create_before_destroy = true
  }
}

# provision the RDS instance
resource "aws_db_instance" "garden_db" {
  db_name               = "garden_db_${var.env}"
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp2"
  engine                = "postgres"
  engine_version        = var.postgres_version
  instance_class        = var.instance_class
  username              = var.db_username
  password              = var.db_password
  parameter_group_name  = "default.postgres${var.postgres_version}"
  skip_final_snapshot   = true
  publicly_accessible   = false

  vpc_security_group_ids = [
    aws_security_group.garden_db_sg.id,
  ]

  tags = {
    Environment = var.env
  }
}
