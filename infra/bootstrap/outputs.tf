output "account_id" {
  description = "AWS account that owns the state bucket."
  value       = data.aws_caller_identity.current.account_id
}

output "state_bucket_name" {
  description = "S3 bucket that stores environment Terraform state."
  value       = aws_s3_bucket.state.id
}

output "state_bucket_region" {
  description = "Region of the Terraform state bucket."
  value       = var.aws_region
}
