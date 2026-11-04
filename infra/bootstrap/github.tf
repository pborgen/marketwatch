# GitHub Actions on main assumes this role and applies infra/envs/dev.
# Apply this stack once from a laptop before the first workflow run. The
# workflow does not apply bootstrap, so it cannot create or widen its own role.

variable "github_repository" {
  type        = string
  description = "GitHub repository (owner/name) allowed to apply the dev environment from main."
  default     = "pborgen/marketwatch"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must look like owner/name."
  }
}

variable "github_owner_id" {
  type        = string
  description = "Numeric GitHub owner id. Actions puts this in the OIDC subject."
  default     = "1530586"
}

variable "github_repository_id" {
  type        = string
  description = "Numeric GitHub repository id. Actions puts this in the OIDC subject."
  default     = "1439897968"
}

locals {
  github_subject = "${split("/", var.github_repository)[0]}@${var.github_owner_id}/${split("/", var.github_repository)[1]}@${var.github_repository_id}"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # The IAM API requires a thumbprint. AWS ignores it for this issuer and
  # validates GitHub's certificate itself.
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

data "aws_iam_policy_document" "github_dev_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # workflow_dispatch from main presents the same subject as a push.
    # GitHub includes the owner id and repository id, so the name-only
    # subject repo:owner/name:ref:refs/heads/main does not match.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.github_subject}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_dev" {
  name                 = "${var.project}-gha-dev"
  description          = "GitHub Actions on main applies infra/envs/dev."
  assume_role_policy   = data.aws_iam_policy_document.github_dev_trust.json
  max_session_duration = 7200
}

# PowerUserAccess covers the dev stack (VPC, ECS, ECR, RDS, OpenSearch, S3,
# CloudFront, logs, Secrets Manager, Bedrock AgentCore) without iam:*.
# Prod is not deployed. The statements below are the boundaries that stay in
# force when it is: this role cannot write prod state, and it can pass or edit
# only marketwatch-dev-* roles.
resource "aws_iam_role_policy_attachment" "github_dev_power_user" {
  role       = aws_iam_role.github_dev.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

data "aws_iam_policy_document" "github_dev" {
  statement {
    sid = "DevRoles"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
      "iam:PassRole",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
    ]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project}-dev-*"]
  }

  statement {
    sid       = "ReadAwsManagedPolicies"
    actions   = ["iam:GetPolicy", "iam:GetPolicyVersion"]
    resources = ["arn:aws:iam::aws:policy/*"]
  }

  statement {
    sid = "ReadOpenSearchServiceRole"
    actions = [
      "iam:GetRole",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
    ]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/opensearchservice.amazonaws.com/*"]
  }

  statement {
    sid       = "PassDevRolesToRuntimeServices"
    effect    = "Deny"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project}-dev-*"]

    condition {
      test     = "StringNotEquals"
      variable = "iam:PassedToService"
      values = [
        "ecs-tasks.amazonaws.com",
        "bedrock-agentcore.amazonaws.com",
      ]
    }
  }

  statement {
    sid    = "DenyProdState"
    effect = "Deny"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.state.arn}/envs/prod/*"]
  }

  statement {
    sid    = "DenyStateBucketChanges"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket",
      "s3:DeleteBucketPolicy",
      "s3:PutBucketPolicy",
      "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration",
      "s3:PutBucketPublicAccessBlock",
    ]
    resources = [aws_s3_bucket.state.arn]
  }

  # PowerUserAccess can delete any service-linked role. Dev apply only needs
  # to read the OpenSearch one, or create it when it is missing.
  statement {
    sid       = "DenyDeleteServiceLinkedRole"
    effect    = "Deny"
    actions   = ["iam:DeleteServiceLinkedRole"]
    resources = ["*"]
  }

  statement {
    sid    = "DenyAssumeOtherRoles"
    effect = "Deny"
    actions = [
      "sts:AssumeRole",
      "sts:AssumeRoleWithSAML",
      "sts:AssumeRoleWithWebIdentity",
      "sts:GetFederationToken",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_dev" {
  name   = "${var.project}-gha-dev"
  role   = aws_iam_role.github_dev.id
  policy = data.aws_iam_policy_document.github_dev.json
}

output "github_dev_deploy_role_arn" {
  description = "GitHub Actions variable AWS_DEPLOY_ROLE_ARN. Pushes to main assume this role and apply infra/envs/dev."
  value       = aws_iam_role.github_dev.arn
}
