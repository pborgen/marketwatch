locals {
  image = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  environment = concat(
    [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
      { name = "PORT", value = "8000" },
    ],
    [for key, value in var.environment : { name = key, value = value }],
  )
}

resource "aws_ecr_repository" "api" {
  name                 = "${var.name}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "terraform_data" "api_image" {
  depends_on = [aws_ecr_repository.api]

  triggers_replace = var.image_tag

  provisioner "local-exec" {
    command     = "bash scripts/deploy/push_api_image.sh"
    working_dir = var.repo_root

    environment = {
      ECR_REPOSITORY_URL = aws_ecr_repository.api.repository_url
      AWS_REGION         = var.aws_region
      IMAGE_TAG          = var.image_tag
      DOCKER_PLATFORM    = var.docker_platform
    }
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}-api"
  retention_in_days = 7
}

data "aws_iam_policy_document" "ecs_tasks" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-api-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid = "ApplicationBucket"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      var.data_bucket_arn,
      "${var.data_bucket_arn}/*",
    ]
  }

  statement {
    sid       = "DatabaseSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }

  statement {
    sid = "OpenSearch"
    actions = [
      "es:ESHttpGet",
      "es:ESHttpHead",
      "es:ESHttpPost",
      "es:ESHttpPut",
      "es:ESHttpPatch",
      "es:ESHttpDelete",
    ]
    resources = ["${var.opensearch_domain_arn}/*"]
  }

  # Strands and deepagents call Bedrock from this task. Model IDs vary by
  # inference profile, so the resource is not pinned to one foundation model.
  statement {
    sid = "BedrockModels"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "${var.name}-api-task"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

resource "aws_lb" "api" {
  name                       = "${var.name}-api"
  load_balancer_type         = "application"
  internal                   = false
  subnets                    = var.public_subnet_ids
  security_groups            = [var.alb_security_group_id]
  drop_invalid_header_fields = true
  enable_deletion_protection = false
}

resource "aws_lb_target_group" "api" {
  name                 = "${var.name}-api"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc_id
  deregistration_delay = 30

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_cluster" "api" {
  name = var.name
}

resource "aws_ecs_task_definition" "api" {
  depends_on = [terraform_data.api_image]

  family                   = "${var.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.image
      essential = true
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      environment = local.environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name             = "${var.name}-api"
  cluster          = aws_ecs_cluster.api.id
  task_definition  = aws_ecs_task_definition.api.arn
  desired_count    = 1
  launch_type      = "FARGATE"
  platform_version = "1.4.0"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.api_security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 60

  depends_on = [aws_lb_listener.http]

  triggers = {
    image_tag = var.image_tag
  }
}
