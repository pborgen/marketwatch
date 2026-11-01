output "vpc_id" {
  description = "VPC for this environment."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Subnets for the load balancer and API tasks."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnets for PostgreSQL and OpenSearch."
  value       = aws_subnet.private[*].id
}

output "db_subnet_group_name" {
  description = "Private subnets for RDS."
  value       = aws_db_subnet_group.this.name
}

output "alb_security_group_id" {
  description = "Security group for the public load balancer."
  value       = aws_security_group.alb.id
}

output "api_security_group_id" {
  description = "Security group for API tasks."
  value       = aws_security_group.api.id
}

output "database_security_group_id" {
  description = "Security group for application PostgreSQL."
  value       = aws_security_group.database.id
}

output "opensearch_security_group_id" {
  description = "Security group for the OpenSearch vector database."
  value       = aws_security_group.opensearch.id
}
