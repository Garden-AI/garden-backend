# creates an application role that the container/task runs as
resource "aws_iam_role" "app_role" {
  name               = "${var.app}-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Effect = "Allow"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  role       = aws_iam_role.app_role.name
}

# assigns the app policy
resource "aws_iam_role_policy" "app_policy" {
  name   = "${var.app}-${var.environment}"
  role   = aws_iam_role.app_role.id
  policy = data.aws_iam_policy_document.app_policy.json
}

data "aws_iam_policy_document" "app_policy" {
  statement {
    actions = [
      "ecs:DescribeClusters",
    ]

    resources = [
      aws_ecs_cluster.app.arn,
    ]
  }
}

data "aws_caller_identity" "current" {
}
