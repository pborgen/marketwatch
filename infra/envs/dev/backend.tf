# Bucket and region come from backend.hcl (gitignored). init.sh writes that file
# once AWS credentials work. The state key stays here so this environment has
# its own state object. Locking uses an S3 lock file (Terraform 1.10+).
terraform {
  backend "s3" {
    key          = "envs/dev/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}
