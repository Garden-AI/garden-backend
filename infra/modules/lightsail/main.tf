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


# IAM stuff
# note: lightsail can't assume iam roles, so we define an iam user here to attach policies to
# but inject the actual credentials for the app at deployment time with the gh action
resource "aws_iam_user" "lightsail_user" {
  name = "garden_lightsail_user_${var.env}"
}
