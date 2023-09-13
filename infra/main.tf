terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0.0"
    }
  }
  required_version = "~> 1.3.0"
  backend "s3" {
    bucket = "garden-backend-terraform-state"
    key    = "garden-backend/s3/terraform.tfstate"
    region = "us-east-1"

    dynamodb_table = "garden-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_secretsmanager_secret" "datacite_endpoint" {
  name = "datacite/endpoint"
}

data "aws_secretsmanager_secret_version" "datacite_endpoint" {
  secret_id = data.aws_secretsmanager_secret.datacite_endpoint.id
}

data "aws_secretsmanager_secret" "datacite_password" {
  name = "datacite/password"
}

data "aws_secretsmanager_secret_version" "datacite_password" {
  secret_id = data.aws_secretsmanager_secret.datacite_password.id
}

data "aws_secretsmanager_secret" "datacite_prefix" {
  name = "datacite/prefix"
}

data "aws_secretsmanager_secret_version" "datacite_prefix" {
  secret_id = data.aws_secretsmanager_secret.datacite_prefix.id
}

data "aws_secretsmanager_secret" "datacite_repo_id" {
  name = "datacite/repo_id"
}

data "aws_secretsmanager_secret_version" "datacite_repo_id" {
  secret_id = data.aws_secretsmanager_secret.datacite_repo_id.id
}

/* Authorizer Lambda */

resource "aws_lambda_function" "garden_authorizer" {
  function_name = "GardenAuthorizer"

  filename = "authorizer.zip"
  runtime  = "python3.9"
  handler  = "lambda_function.lambda_handler"

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_cloudwatch_log_group" "garden_authorizer" {
  name = "/aws/lambda/${aws_lambda_function.garden_authorizer.function_name}"

  retention_in_days = 30
}

/* App Lambda */

resource "aws_lambda_function" "garden_app" {
  function_name = "GardenApp"

  filename = "app.zip"
  runtime  = "python3.9"
  handler  = "lambda_function.lambda_handler"

  role    = aws_iam_role.lambda_exec.arn
  timeout = 10
}

resource "aws_cloudwatch_log_group" "garden_app" {
  name = "/aws/lambda/${aws_lambda_function.garden_app.function_name}"

  retention_in_days = 30
}

/* API Gateway */

module "api_gateway" {
  source                          = "./modules/api_gateway"
  env                             = var.env
  api_cert_arn                    = data.aws_acm_certificate.api_cert.arn
  api_cert_domain                 = data.aws_acm_certificate.api_cert.domain
  garden_app_invoke_arn           = aws_lambda_function.garden_app.invoke_arn
  garden_app_function_name        = aws_lambda_function.garden_app.function_name
  garden_authorizer_invoke_arn    = aws_lambda_function.garden_authorizer.invoke_arn
  garden_authorizer_function_name = aws_lambda_function.garden_authorizer.function_name
}



/* Connect api.thegardens.ai to the gateway */

data "aws_route53_zone" "hosted_zone" {
  name = "thegardens.ai"
}

data "aws_acm_certificate" "api_cert" {
  domain = "api.thegardens.ai"
}


resource "aws_route53_record" "api_record" {
  name    = module.api_gateway.api_domain_name
  type    = "A"
  zone_id = data.aws_route53_zone.hosted_zone.id

  alias {
    evaluate_target_health = true
    name                   = module.api_gateway.api_cloudfront_domain_name
    zone_id                = module.api_gateway.api_cloudfront_zone_id
  }
}

/* Connect the auth/app Lambdas to the gateway */

resource "aws_lambda_permission" "garden_api_auth_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_authorizer.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${module.api_gateway.api_execution_arn}/*/*"
}

resource "aws_lambda_permission" "garden_api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_app.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${module.api_gateway.api_execution_arn}/*/*"
}

/* Shared Lambda resources */

resource "aws_iam_role" "lambda_exec" {
  name = "garden_lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Sid    = ""
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      }
    ]
  })
}

resource "aws_iam_policy" "allow_globus_api_key_access_policy" {
  name        = "test-policy"
  description = "A test policy"

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Action" : [
          "secretsmanager:GetSecretValue"
        ],
        "Resource" : [
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/repo_id-ePlB1w",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/password-FFLiwt",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/endpoint-06aepz",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:datacite/prefix-K6GdzM",
          "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:garden/globus_api-2YYuTW"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "globus_secret_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.allow_globus_api_key_access_policy.arn
}

resource "aws_iam_role_policy_attachment" "s3_full_access_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.s3_full_access.arn
}
