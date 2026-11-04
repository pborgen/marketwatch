data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  image      = "${aws_ecr_repository.agent.repository_url}:${var.image_tag}"
}

resource "aws_ecr_repository" "agent" {
  name                 = "${var.name}-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "terraform_data" "agent_image" {
  depends_on = [aws_ecr_repository.agent]

  triggers_replace = var.image_tag

  provisioner "local-exec" {
    command     = "bash scripts/deploy/push_agent_image.sh"
    working_dir = var.repo_root

    environment = merge(
      {
        ECR_REPOSITORY_URL = aws_ecr_repository.agent.repository_url
        AWS_REGION         = var.aws_region
        IMAGE_TAG          = var.image_tag
        # AgentCore only runs ARM64 images.
        DOCKER_PLATFORM = "linux/arm64"
      },
      # The demo image is the script default, so its provisioner env stays unchanged.
      { for key, value in { AGENT_DOCKERFILE = var.dockerfile } : key => value if value != "apps/agents/demo/Dockerfile" },
    )
  }
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-agent"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "ECRToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "ECRImage"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [aws_ecr_repository.agent.arn]
  }

  statement {
    sid = "RuntimeLogs"
    actions = [
      "logs:DescribeLogStreams",
      "logs:CreateLogGroup",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
    ]
  }

  statement {
    sid = "RuntimeLogPolicy"
    actions = [
      "logs:PutResourcePolicy",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/${var.runtime_name}-*",
    ]
  }

  statement {
    sid       = "DescribeLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*"]
  }

  statement {
    sid = "WriteRuntimeLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
    ]
  }

  statement {
    sid = "Traces"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "RuntimeMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  statement {
    sid = "WorkloadToken"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
      "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:workload-identity-directory/default/workload-identity/${var.runtime_name}-*",
    ]
  }

  # Strands calls the Bedrock Converse API. Inference profile ids differ from
  # foundation-model ids, so the account-scoped resource stays broad.
  statement {
    sid = "BedrockModels"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream",
    ]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${var.aws_region}:${local.account_id}:*",
    ]
  }

  dynamic "statement" {
    for_each = var.data_bucket_arn == "" ? [] : [var.data_bucket_arn]
    content {
      sid       = "EventsBucketList"
      actions   = ["s3:ListBucket"]
      resources = [statement.value]
    }
  }

  # Prompt management is a separate API from Converse. The agent reads one
  # numbered version at startup and uses the text as its system prompt.
  dynamic "statement" {
    for_each = length(var.bedrock_prompt_arns) == 0 ? [] : [var.bedrock_prompt_arns]
    content {
      sid       = "BedrockPrompt"
      actions   = ["bedrock:GetPrompt"]
      resources = statement.value
    }
  }

  dynamic "statement" {
    for_each = var.data_bucket_arn == "" ? [] : [var.data_bucket_arn]
    content {
      sid = "EventsBucketObjects"
      actions = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:AbortMultipartUpload",
      ]
      resources = ["${statement.value}/*"]
    }
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "${var.name}-agent"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = var.runtime_name
  description        = var.description
  role_arn           = aws_iam_role.execution.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = local.image
    }
  }

  environment_variables = merge(
    {
      AWS_REGION         = var.aws_region
      AWS_DEFAULT_REGION = var.aws_region
      STRANDS_MODEL_ID   = var.model_id
    },
    { for key, value in { DATA_BUCKET = var.data_bucket_name } : key => value if value != "" },
    { for key, value in { BEDROCK_PROMPT_ID = var.bedrock_prompt_id } : key => value if value != "" },
    { for key, value in { BEDROCK_PROMPT_VERSION = var.bedrock_prompt_version } : key => value if value != "" },
  )

  network_configuration {
    network_mode = "PUBLIC"
  }

  lifecycle_configuration {
    idle_runtime_session_timeout = 900
    max_lifetime                 = 3600
  }

  depends_on = [
    terraform_data.agent_image,
    aws_iam_role_policy.execution,
  ]
}
