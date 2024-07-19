data "aws_secretsmanager_secret" "datacite_endpoint" {
  name = "datacite/endpoint-${var.env}"
}
data "aws_secretsmanager_secret_version" "datacite_endpoint" {
  secret_id = data.aws_secretsmanager_secret.datacite_endpoint.id
}

data "aws_secretsmanager_secret" "datacite_password" {
  name = "datacite/password-${var.env}"
}
data "aws_secretsmanager_secret_version" "datacite_password" {
  secret_id = data.aws_secretsmanager_secret.datacite_password.id
}

data "aws_secretsmanager_secret" "datacite_prefix" {
  name = "datacite/prefix-${var.env}"
}
data "aws_secretsmanager_secret_version" "datacite_prefix" {
  secret_id = data.aws_secretsmanager_secret.datacite_prefix.id
}

data "aws_secretsmanager_secret" "datacite_repo_id" {
  name = "datacite/repo_id-${var.env}"
}
data "aws_secretsmanager_secret_version" "datacite_repo_id" {
  secret_id = data.aws_secretsmanager_secret.datacite_repo_id.id
}


resource "aws_iam_policy" "allow_globus_api_key_access_policy" {
  name        = "test-policy-${var.env}"
  description = "A test policy"
  tags        = var.tags

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Action" : [
          "secretsmanager:GetSecretValue"
        ],
        "Resource" : [
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/endpoint-${var.env}-*",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/password-${var.env}-*",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/prefix-${var.env}-*",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/repo_id-${var.env}-*",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:garden/globus_api-2YYuTW"
        ]
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "globus_secret_policy" {
  user       = var.lightsail_iam_user_name
  policy_arn = aws_iam_policy.allow_globus_api_key_access_policy.arn
}

# note: this secret is read directly by the backend app to set its environment
# variables; these data sources are here to grab the DB_USERNAME/DB_PASSWORD
# values we can then pass to the terraform resources for the database itself
data "aws_secretsmanager_secret" "backend_env_vars" {
  name = "garden-backend-env-vars/${var.env}"
}

data "aws_secretsmanager_secret_version" "current" {
  secret_id = data.aws_secretsmanager_secret.backend_env_vars.id
}
