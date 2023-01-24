terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0.0"
    }
  }
  required_version = "~> 1.0"
}

provider "aws" {
  region = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "The id of the team's AWS account"
}

variable "globus_auth_secret_name" {
  type        = string
  description = "The id of the team's AWS account"
}

/* Authorizer Lambda */

resource "aws_lambda_function" "garden_authorizer" {
  function_name = "GardenAuthorizer"

  filename = "authorizer.zip"
  runtime = "python3.9"
  handler = "lambda_function.lambda_handler"

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
  runtime = "python3.9"
  handler = "lambda_function.lambda_handler"

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_cloudwatch_log_group" "garden_app" {
  name = "/aws/lambda/${aws_lambda_function.garden_app.function_name}"

  retention_in_days = 30
}

/* API Gateway */

resource "aws_api_gateway_rest_api" "garden_api" {
  name          = "garden_gateway"
}

resource "aws_api_gateway_stage" "garden_api" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  deployment_id = aws_api_gateway_deployment.garden_deployment.id

  stage_name        = "garden_prod"

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.garden_api_gw.arn

    format = jsonencode({
      requestId               = "$context.requestId"
      sourceIp                = "$context.identity.sourceIp"
      httpMethod              = "$context.httpMethod"
      resourcePath            = "$context.resourcePath"
      routeKey                = "$context.routeKey"
      status                  = "$context.status"
      responseLength          = "$context.responseLength"
      integrationErrorMessage = "$context.integrationErrorMessage"
      protocol                = "$context.protocol"
      requestTime             = "$context.requestTime"
      integrationRequestId    = "$context.integration.requestId"
      functionResponseStatus  = "$context.integration.status"
      integrationLatency      = "$context.integration.latency"
      integrationServiceStatus= "$context.integration.integrationStatus"
      xrayTraceId             = "$context.xrayTraceId"
      responseLatency         = "$context.responseLatency"
      path                    = "$context.path"
      authorizeResultStatus   = "$context.authorize.status"
      authorizerServiceStatus = "$context.authorizer.status"
      authorizerLatency       = "$context.authorizer.latency"
      authorizerRequestId     = "$context.authorizer.requestId"
      }
    )
  }
}

resource "aws_api_gateway_deployment" "garden_deployment" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  description = "Terraform managed deployment"

  triggers = {
    # NOTE: The configuration below will satisfy ordering considerations,
    #       but not pick up all future REST API changes. More advanced patterns
    #       are possible, such as using the filesha1() function against the
    #       Terraform configuration file(s) or removing the .id references to
    #       calculate a hash against whole resources. Be aware that using whole
    #       resources will show a difference after the initial implementation.
    #       It will stabilize to only change when resources change afterwards.
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.garden_app.id,
      aws_api_gateway_method.garden_auth_hookup.id,
      aws_api_gateway_integration.garden_app.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_cloudwatch_log_group" "garden_api_gw" {
  name = "/aws/garden_api_gw/${aws_api_gateway_rest_api.garden_api.name}"

  retention_in_days = 30
}

/* Connect the authorizer Lambda to the gateway */

resource "aws_api_gateway_authorizer" "garden_authorizer" {
  rest_api_id                       = aws_api_gateway_rest_api.garden_api.id
  type                              = "REQUEST"
  authorizer_uri                    = aws_lambda_function.garden_authorizer.invoke_arn
  name                              = aws_lambda_function.garden_authorizer.function_name
}

resource "aws_api_gateway_method" "garden_auth_hookup" {
  authorization = "CUSTOM"
  http_method   = "ANY"
  authorizer_id = aws_api_gateway_authorizer.garden_authorizer.id
  resource_id   = aws_api_gateway_resource.garden_app.id
  rest_api_id   = aws_api_gateway_rest_api.garden_api.id
}

resource "aws_lambda_permission" "garden_api_auth_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_authorizer.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_rest_api.garden_api.execution_arn}/*/*"
}

/* Connect the app Lambda to the gateway */

resource "aws_api_gateway_resource" "garden_app" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  parent_id = aws_api_gateway_rest_api.garden_api.root_resource_id

  path_part = "{proxy+}"
}

resource "aws_api_gateway_integration" "garden_app" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  resource_id = aws_api_gateway_resource.garden_app.id
  http_method = "ANY"
  type = "AWS_PROXY"
  integration_http_method = "POST"
  uri    = aws_lambda_function.garden_app.invoke_arn
  depends_on = [
    aws_api_gateway_resource.garden_app
  ]
}

resource "aws_lambda_permission" "garden_api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_app.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_rest_api.garden_api.execution_arn}/*/*"
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
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:us-east-1:${var.aws_account_id}:secret:${var.globus_auth_secret_name}"
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