output "web_url" {
  description = "Agent monitor. Sign in with the monitor_password variable."
  value       = module.web.url
}

output "api_url" {
  description = "API load balancer. The monitor is also served here."
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

output "agent_runtime_arn" {
  description = "AgentCore runtime for the market-watch demo."
  value       = module.agent.agent_runtime_arn
}

output "events_agent_runtime_arn" {
  description = "AgentCore runtime that stores current events in the data bucket."
  value       = module.events_agent.agent_runtime_arn
}

output "events_system_prompt_arn" {
  description = "Numbered Bedrock prompt version the current-events runtime loads."
  value       = local.events_system_prompt_version["Arn"]
}
