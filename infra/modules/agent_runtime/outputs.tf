output "agent_runtime_arn" {
  description = "ARN passed to bedrock-agentcore invoke-agent-runtime."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "AgentCore runtime id."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
}

output "repository_url" {
  description = "ECR repository for the agent image."
  value       = aws_ecr_repository.agent.repository_url
}
