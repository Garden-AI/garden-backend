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


resource "aws_lightsail_container_service_deployment_version" "garden_service_deployment" {
  service_name = aws_lightsail_container_service.garden_service.name
  container {
    container_name = "garden-backend-service"
    image          = "gardenai/garden-service:latest"
    ports = {
      80 = "HTTP"
    }
    environment = {
      GARDEN_ENV = "${var.env}"
    }
  }

  public_endpoint {
    container_name = "garden-backend-service"
    container_port = 80
    health_check {
      healthy_threshold   = 2
      unhealthy_threshold = 2
      timeout_seconds     = 2
      interval_seconds    = 5
      path                = "/"
    }
  }
}
