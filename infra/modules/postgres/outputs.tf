output "address" {
  description = "Hostname API tasks use to connect."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "PostgreSQL port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN for the master password. RDS generates the secret."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
