# Local state on purpose. This stack creates the remote state bucket, so it
# cannot store its own state there. Keep terraform.tfstate after the first apply.
terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
