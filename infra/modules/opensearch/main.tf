data "aws_caller_identity" "current" {}

resource "aws_iam_service_linked_role" "opensearch" {
  aws_service_name = "opensearchservice.amazonaws.com"
}

resource "aws_opensearch_domain" "this" {
  domain_name    = var.name
  engine_version = "OpenSearch_3.7"

  cluster_config {
    instance_type            = "t3.small.search"
    instance_count           = 1
    dedicated_master_enabled = false
    zone_awareness_enabled   = false
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = 10
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  vpc_options {
    subnet_ids         = [var.subnet_id]
    security_group_ids = [var.security_group_id]
  }

  # The security group only admits the API. This policy then allows IAM in the
  # account; the task role still needs es:ESHttp* on the domain.
  access_policies = data.aws_iam_policy_document.this.json

  auto_tune_options {
    desired_state = "DISABLED"
  }

  depends_on = [aws_iam_service_linked_role.opensearch]
}

data "aws_iam_policy_document" "this" {
  statement {
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["es:*"]
    resources = ["arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/${var.name}/*"]
  }
}
