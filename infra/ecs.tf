/**
 * Elastic Container Service (ecs)
 * This component is required to create the Fargate ECS service. It will create a Fargate cluster
 * based on the application name and enironment. It will create a "Task Definition", which is required
 * to run a Docker container, https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html.
 * Next it creates a ECS Service, https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html
 * It attaches the Load Balancer created in `lb.tf` to the service, and sets up the networking required.
 * It also creates a role with the correct permissions. And lastly, ensures that logs are captured in CloudWatch.
 */

# How many containers to run
variable "replicas" {
  default = "1"
}

# The name of the container to run
variable "container_name" {
  default = "mlflow"
}

# The minimum number of containers that should be running.
# Must be at least 1.
# used by both autoscale-perf.tf and autoscale.time.tf
# For production, consider using at least "2".
variable "ecs_autoscale_min_instances" {
  default = "1"
}

# The maximum number of containers that should be running.
# used by both autoscale-perf.tf and autoscale.time.tf
variable "ecs_autoscale_max_instances" {
  default = "8"
}

resource "aws_ecs_cluster" "app" {
  name = "${var.app}-${var.environment}"
  tags = var.tags
}

resource "aws_appautoscaling_target" "app_scale_target" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.app.name}/${aws_ecs_service.app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  max_capacity       = var.ecs_autoscale_max_instances
  min_capacity       = var.ecs_autoscale_min_instances
}

data "aws_secretsmanager_secret" "db_password" {
  name = "mlflow/store-db-password"
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = data.aws_secretsmanager_secret.db_password.id
}

resource "aws_ecs_task_definition" "mlflow" {
  family = "mlflow"
  container_definitions = jsonencode(concat([
    {
      name      = "mlflow"
      image     = "gcr.io/getindata-images-public/mlflow:1.24.0"
      essential = true

      entryPoint = ["sh", "-c"]
      command = [
        <<EOT
        /bin/sh -c "mlflow server \
          --host=0.0.0.0 \
          --port=${var.container_port} \
          --artifacts-destination=s3://${aws_s3_bucket.artifacts.bucket}${var.artifact_bucket_path} \
          --serve-artifacts \
          --backend-store-uri=mysql+pymysql://${aws_rds_cluster.backend_store.master_username}:`echo -n $DB_PASSWORD`@${aws_rds_cluster.backend_store.endpoint}:${aws_rds_cluster.backend_store.port}/${aws_rds_cluster.backend_store.database_name} \
          --gunicorn-opts '${var.gunicorn_opts}'"
        EOT
      ]

      portMappings = [{ containerPort = var.container_port, hostPort = var.container_port }]
      environment = [
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.region
        },
      ]
      secrets = [
        {
          name      = "DB_PASSWORD"
          valueFrom = data.aws_secretsmanager_secret.db_password.arn
        }
      ]
      logConfiguration = {
        logDriver     = "awslogs"
        secretOptions = null
        options = {
          "awslogs-group"         = "/fargate/service/mlflow-prod"
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ]))

  network_mode             = "awsvpc"
  task_role_arn            = aws_iam_role.app_role.arn
  execution_role_arn       = aws_iam_role.ecsTaskExecutionRole.arn
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.service_cpu
  memory                   = var.service_memory
}

resource "aws_iam_role_policy" "secrets" {
  name = "${var.unique_name}-read-secret"
  role = aws_iam_role.ecsTaskExecutionRole.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetResourcePolicy",
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecretVersionIds",
        ]
        Resource = [
          data.aws_secretsmanager_secret_version.db_password.arn,
        ]
      },
    ]
  })
}

resource "aws_ecs_service" "app" {
  name            = "${var.app}-${var.environment}"
  cluster         = aws_ecs_cluster.app.id
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = var.replicas

  network_configuration {
    security_groups = [aws_security_group.nsg_task.id]
    subnets         = split(",", var.private_subnets)
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.id
    container_name   = var.container_name
    container_port   = var.container_port
  }

  tags                    = var.tags
  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  # workaround for https://github.com/hashicorp/terraform/issues/12634
  depends_on = [aws_lb_listener.tcp]

}

# https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html
resource "aws_iam_role" "ecsTaskExecutionRole" {
  name               = "${var.app}-${var.environment}-ecs"
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json
}

data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "ecsTaskExecutionRole_policy" {
  role       = aws_iam_role.ecsTaskExecutionRole.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

variable "logs_retention_in_days" {
  type        = number
  default     = 90
  description = "Specifies the number of days you want to retain log events"
}

resource "aws_cloudwatch_log_group" "logs" {
  name              = "/fargate/service/${var.app}-${var.environment}"
  retention_in_days = var.logs_retention_in_days
  tags              = var.tags
}