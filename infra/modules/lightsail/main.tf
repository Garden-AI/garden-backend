resource "aws_lightsail_container_service" "garden_service" {
  name        = "garden-service-${var.env}"
  power       = "micro"
  scale       = 1
  is_disabled = false

  tags = {
    Component   = "Lightsail Container Service"
    Project     = "Garden"
    Environment = "${var.env}"
  }
}
