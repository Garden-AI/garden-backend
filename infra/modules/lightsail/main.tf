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
# but inject the actual user credentials for the app at deployment time with the gh action
resource "aws_iam_user" "lightsail_user" {
  name = "garden_lightsail_user_${var.env}"
}

data "aws_iam_policy_document" "secrets_policy" {
  statement {
    sid       = "AllowReadSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:garden-backend-env-vars/${var.env}-*"]
  }
}

resource "aws_iam_policy" "secrets_policy" {
  name        = "secrets_policy_${var.env}"
  description = "A policy that allows IAM user to read a secret"
  policy      = data.aws_iam_policy_document.secrets_policy.json
}

resource "aws_iam_user_policy_attachment" "lightsail_user_secrets_policy_attachment" {
  user       = aws_iam_user.lightsail_user.name
  policy_arn = aws_iam_policy.secrets_policy.arn
}
