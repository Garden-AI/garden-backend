
resource "aws_api_gateway_rest_api" "garden_api" {
  name               = "garden_gateway_${var.env}"
  binary_media_types = ["application/octet-stream"]
}

resource "aws_api_gateway_stage" "garden_api" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  deployment_id = aws_api_gateway_deployment.garden_deployment.id

  stage_name        = "garden_${var.env}"

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
      aws_api_gateway_rest_api.garden_api,
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


resource "aws_api_gateway_resource" "garden_app" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  parent_id = aws_api_gateway_rest_api.garden_api.root_resource_id

  path_part = "{proxy+}"
}

/* Connect the authorizer Lambda to the gateway */

resource "aws_api_gateway_authorizer" "garden_authorizer" {
  rest_api_id                       = aws_api_gateway_rest_api.garden_api.id
  type                              = "REQUEST"
  authorizer_uri                    = var.garden_authorizer_invoke_arn
  name                              = var.garden_authorizer_function_name
}

resource "aws_api_gateway_method" "garden_auth_hookup" {
  authorization = "CUSTOM"
  http_method   = "ANY"
  authorizer_id = aws_api_gateway_authorizer.garden_authorizer.id
  resource_id   = aws_api_gateway_resource.garden_app.id
  rest_api_id   = aws_api_gateway_rest_api.garden_api.id
}

resource "aws_api_gateway_integration" "garden_app" {
  rest_api_id = aws_api_gateway_rest_api.garden_api.id
  resource_id = aws_api_gateway_resource.garden_app.id
  http_method = "ANY"
  type = "AWS_PROXY"
  integration_http_method = "POST"
  uri    = var.garden_app_invoke_arn
  depends_on = [
    aws_api_gateway_resource.garden_app
  ]
}
