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

# duplicated from lambda module
# define "ecr-pusher" role for lightsail user to assume
resource "aws_iam_role" "assumable_role" {
  name = "ecr-pusher-${var.env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          AWS = [
            aws_iam_user.lightsail_user.arn
          ]
        },
      },
    ],
  })
}

# attach ecr backend write policy to assumable role
resource "aws_iam_role_policy_attachment" "ecr_access_attach" {
  role       = aws_iam_role.assumable_role.name
  policy_arn = var.ecr_access_policy_arn
}

# make and attach policy allowing lightsail IAM user to assume role
data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]
    resources = [aws_iam_role.assumable_role.arn]
  }
}

resource "aws_iam_policy" "allow_assume_role_policy" {
  name = "allow_assume_role_policy_${var.env}"
  policy = data.aws_iam_policy_document.assume_role_policy.json
}

resource "aws_iam_user_policy_attachment" "allow_assume_role_attachment" {
  user = aws_iam_user.lightsail_user.name
  policy_arn = aws_iam_policy.allow_assume_role_policy.arn
}

resource "aws_iam_user_policy_attachment" "s3_access_attachment" {
  user = aws_iam_user.lightsail_user.name
  policy_arn = var.s3_access_policy_arn
}
