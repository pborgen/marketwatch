data "aws_caller_identity" "current" {}

locals {
  name      = "${var.project}-${var.environment}"
  repo_root = abspath("${path.module}/../../..")
  web_source_files = [
    for path in fileset("${local.repo_root}/apps/web", "**") : "${local.repo_root}/apps/web/${path}"
    if !startswith(path, "node_modules/") && !startswith(path, "dist/")
  ]
  api_image_tag = substr(sha256(join("", concat([
    filesha256("${path.module}/../../../apps/api/main.py"),
    filesha256("${path.module}/../../../apps/api/auth.py"),
    filesha256("${path.module}/../../../apps/api/agents.py"),
    filesha256("${path.module}/../../../apps/api/Dockerfile"),
  ], [for path in sort(local.web_source_files) : filesha256(path)]))), 0, 12)
  agent_source_files = [
    for path in concat(
      [for path in fileset("${local.repo_root}/apps/agents/demo", "**") : "${local.repo_root}/apps/agents/demo/${path}"],
      [for path in fileset("${local.repo_root}/packages/datafeed", "**") : "${local.repo_root}/packages/datafeed/${path}"],
      [for path in fileset("${local.repo_root}/packages/envfile", "**") : "${local.repo_root}/packages/envfile/${path}"],
    ) : path
    if !endswith(path, ".pyc") && !strcontains(path, "__pycache__") && !strcontains(path, ".env")
  ]
  agent_image_tag = substr(sha256(join("", [for path in sort(local.agent_source_files) : filesha256(path)])), 0, 12)
  # system_prompt.txt is published as a Bedrock prompt version. The image
  # loads that version, so a prompt edit does not rebuild the container.
  events_source_files = [
    for path in concat(
      [for path in fileset("${local.repo_root}/apps/agents/current_events", "**") : "${local.repo_root}/apps/agents/current_events/${path}"],
      [for path in fileset("${local.repo_root}/packages/datafeed", "**") : "${local.repo_root}/packages/datafeed/${path}"],
      [for path in fileset("${local.repo_root}/packages/envfile", "**") : "${local.repo_root}/packages/envfile/${path}"],
    ) : path
    if !endswith(path, ".pyc") && !strcontains(path, "__pycache__") && !strcontains(path, ".env") && !endswith(path, "/system_prompt.txt")
  ]
  events_image_tag = substr(sha256(join("", [for path in sort(local.events_source_files) : filesha256(path)])), 0, 12)
}

module "network" {
  source = "../../modules/network"

  name = local.name
}

module "data_bucket" {
  source = "../../modules/s3_bucket"

  name = "${local.name}-data-${data.aws_caller_identity.current.account_id}"
}

module "web" {
  source = "../../modules/frontend"

  name               = "${local.name}-web"
  origin_domain_name = module.api.dns_name
}

module "postgres" {
  source = "../../modules/postgres"

  name              = "${local.name}-postgres"
  database_name     = "marketwatch"
  subnet_group_name = module.network.db_subnet_group_name
  security_group_id = module.network.database_security_group_id
}

module "opensearch" {
  source = "../../modules/opensearch"

  name              = "${local.name}-vectors"
  aws_region        = var.aws_region
  subnet_id         = module.network.private_subnet_ids[0]
  security_group_id = module.network.opensearch_security_group_id
}

module "api" {
  source = "../../modules/ecs_api"

  name                  = local.name
  aws_region            = var.aws_region
  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  alb_security_group_id = module.network.alb_security_group_id
  api_security_group_id = module.network.api_security_group_id
  image_tag             = local.api_image_tag
  repo_root             = local.repo_root
  data_bucket_arn       = module.data_bucket.bucket_arn
  opensearch_domain_arn = module.opensearch.domain_arn
  secret_arns           = [module.postgres.master_user_secret_arn]
  environment = {
    DATA_BUCKET              = module.data_bucket.bucket_name
    DB_HOST                  = module.postgres.address
    DB_PORT                  = tostring(module.postgres.port)
    DB_NAME                  = module.postgres.database_name
    DB_SECRET_ARN            = module.postgres.master_user_secret_arn
    OPENSEARCH_ENDPOINT      = module.opensearch.endpoint
    MONITOR_PASSWORD         = var.monitor_password
    DEMO_AGENT_RUNTIME_ARN   = module.agent.agent_runtime_arn
    EVENTS_AGENT_RUNTIME_ARN = module.events_agent.agent_runtime_arn
  }
}

module "agent" {
  source = "../../modules/agent_runtime"

  name         = local.name
  runtime_name = replace(local.name, "-", "_")
  aws_region   = var.aws_region
  image_tag    = local.agent_image_tag
  repo_root    = local.repo_root
  model_id     = "us.amazon.nova-micro-v1:0"
}

module "events_agent" {
  source = "../../modules/agent_runtime"

  name                   = "${local.name}-events"
  runtime_name           = "${replace(local.name, "-", "_")}_events"
  aws_region             = var.aws_region
  image_tag              = local.events_image_tag
  repo_root              = local.repo_root
  model_id               = "us.amazon.nova-micro-v1:0"
  dockerfile             = "apps/agents/current_events/Dockerfile"
  description            = "Collects current events into S3 for the OpenSearch RAG index."
  data_bucket_arn        = module.data_bucket.bucket_arn
  data_bucket_name       = module.data_bucket.bucket_name
  bedrock_prompt_id      = aws_bedrockagent_prompt.events_system.id
  bedrock_prompt_version = local.events_system_prompt_version["Version"]
  bedrock_prompt_arns = [
    aws_bedrockagent_prompt.events_system.arn,
    local.events_system_prompt_version["Arn"],
  ]
}
