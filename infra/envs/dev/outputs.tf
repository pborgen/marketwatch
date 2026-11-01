output "web_url" {
  description = "Hello-world frontend."
  value       = module.web.url
}

output "api_url" {
  description = "Hello-world API on ECS."
  value       = module.api.url
}

output "data_bucket_name" {
  description = "Private bucket for application and agent objects."
  value       = module.data_bucket.bucket_name
}

output "postgres_address" {
  description = "Application PostgreSQL hostname."
  value       = module.postgres.address
}

output "postgres_secret_arn" {
  description = "Secret for the application database password."
  value       = module.postgres.master_user_secret_arn
}

output "opensearch_endpoint" {
  description = "OpenSearch vector database endpoint."
  value       = module.opensearch.endpoint
}
