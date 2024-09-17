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
    Project     = "Garden"
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
    Project     = "Garden"
  }

  # enable automatic backups
  backup_retention_period = 14
  backup_window = "00:00-01:00"
}


# Lookup ubuntu ami
data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}


# Create a security group for incoming ssh connections
resource "aws_security_group" "bastion_sg" {
  name = "garden_db_bastion_sg_${var.env}"

  # Accept incoming traffic on port 22
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow outgoing traffic to port 5432
  egress {
    from_port   = 0
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.env
    Project     = "Garden"
  }
}


# Provision the EC2 instance
resource "aws_instance" "rds_bastion" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.micro"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.bastion_sg.id]

  tags = {
    Environment = var.env
    Name        = "rds_bastion_${var.env}"
    Project     = "Garden"
  }
}


# Add the bastion host's private IP to the RDS security group ingress
resource "aws_security_group_rule" "bastion_to_rds" {
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  cidr_blocks       = ["${aws_instance.rds_bastion.private_ip}/32"]
  security_group_id = aws_security_group.garden_db_sg.id
}
