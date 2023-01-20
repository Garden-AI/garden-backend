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

/* New stuff */

resource "aws_lambda_function" "garden_authorizer" {
  function_name = "GardenAuthorizer"

  layers = ["arn:aws:lambda:us-east-1:557062710055:layer:GlobusLayer:92"]
  filename = "authorizer.zip"
  runtime = "python3.9"
  handler = "lambda_function.lambda_handler"

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_cloudwatch_log_group" "garden_authorizer" {
  name = "/aws/lambda/${aws_lambda_function.garden_authorizer.function_name}"

  retention_in_days = 30
}

resource "aws_apigatewayv2_authorizer" "garden_authorizer" {
  api_id                            = aws_apigatewayv2_api.garden_api.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = aws_lambda_function.garden_authorizer.invoke_arn
  identity_sources                  = ["$request.header.Authorization"]
  name                              = aws_lambda_function.garden_authorizer.function_name
  authorizer_payload_format_version = "2.0"
}

#resource "aws_apigatewayv2_integration" "garden_authorizer" {
#  api_id = aws_apigatewayv2_api.garden_api.id
#
#  integration_uri    = aws_lambda_function.garden_authorizer.invoke_arn
#  integration_type   = "AWS_PROXY"
#  integration_method = "POST"
#}

/* End new stuff */

resource "aws_lambda_function" "garden_app" {
  function_name = "GardenApp"

  layers = ["arn:aws:lambda:us-east-1:557062710055:layer:GlobusLayer:92"]
  filename = "app.zip"
  runtime = "python3.9"
  handler = "lambda_function.lambda_handler"

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_cloudwatch_log_group" "garden_app" {
  name = "/aws/lambda/${aws_lambda_function.garden_app.function_name}"

  retention_in_days = 30
}

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

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_apigatewayv2_api" "garden_api" {
  name          = "garden_gateway"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "garden_api" {
  api_id = aws_apigatewayv2_api.garden_api.id

  name        = "garden_stage"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.garden_api_gw.arn

    format = jsonencode({
      requestId               = "$context.requestId"
      sourceIp                = "$context.identity.sourceIp"
      requestTime             = "$context.requestTime"
      protocol                = "$context.protocol"
      httpMethod              = "$context.httpMethod"
      resourcePath            = "$context.resourcePath"
      routeKey                = "$context.routeKey"
      status                  = "$context.status"
      responseLength          = "$context.responseLength"
      integrationErrorMessage = "$context.integrationErrorMessage"
      }
    )
  }
}

resource "aws_apigatewayv2_integration" "garden_app" {
  api_id = aws_apigatewayv2_api.garden_api.id

  integration_uri    = aws_lambda_function.garden_app.invoke_arn
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "garden_app" {
  api_id = aws_apigatewayv2_api.garden_api.id

  route_key = "ANY /api"
  authorization_type = "CUSTOM"
  authorizer_id = aws_apigatewayv2_authorizer.garden_authorizer.id
  target    = "integrations/${aws_apigatewayv2_integration.garden_app.id}"
}

resource "aws_cloudwatch_log_group" "garden_api_gw" {
  name = "/aws/garden_api_gw/${aws_apigatewayv2_api.garden_api.name}"

  retention_in_days = 30
}

resource "aws_lambda_permission" "garden_api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.garden_app.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.garden_api.execution_arn}/*/*"
}