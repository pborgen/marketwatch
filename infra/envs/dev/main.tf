data "aws_caller_identity" "current" {}

locals {
  name      = "${var.project}-${var.environment}"
  repo_root = abspath("${path.module}/../../..")
  api_image_tag = substr(sha256(join("", [
    filesha256("${path.module}/../../../apps/api/main.py"),
    filesha256("${path.module}/../../../apps/api/Dockerfile"),
  ])), 0, 12)
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

  name            = "${local.name}-web-${data.aws_caller_identity.current.account_id}"
  index_html_path = "${local.repo_root}/apps/web/index.html"
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
    DATA_BUCKET         = module.data_bucket.bucket_name
    DB_HOST             = module.postgres.address
    DB_PORT             = tostring(module.postgres.port)
    DB_NAME             = module.postgres.database_name
    DB_SECRET_ARN       = module.postgres.master_user_secret_arn
    OPENSEARCH_ENDPOINT = module.opensearch.endpoint
  }
}
