#!/usr/bin/env bash
# Deploy Market Watch infrastructure.
#
#   AWS_PROFILE=dev bash init-market-watch.sh
#   AWS_PROFILE=dev bash init-market-watch.sh prod --yes
#
# Run bash init.sh first. This applies infra/bootstrap (the Terraform state
# bucket), then infra/envs/<env>. The default environment is dev.
#
# Dev creates the hello-world site, the ECS API, PostgreSQL, an OpenSearch
# vector domain, and the application S3 bucket. Docker
# must be running so apply can publish apps/api.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export TF_IN_AUTOMATION=1

env_name="dev"
assume_yes=0

usage() {
  cat <<'EOF'
Usage: bash init-market-watch.sh [dev|prod] [--yes]

  dev|prod  Environment to apply. Default is dev.
  --yes     Skip the confirmation prompt.
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    dev|prod) env_name="$1" ;;
    --yes) assume_yes=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
  shift
done

command -v terraform >/dev/null 2>&1 || die "Terraform is missing. Run bash init.sh first."
command -v aws >/dev/null 2>&1 || die "The AWS CLI is missing. Run bash init.sh first."

if [[ "$env_name" == "dev" ]]; then
  command -v docker >/dev/null 2>&1 || die "Docker is required to publish the API image for dev."
  docker info >/dev/null 2>&1 || die "Docker is installed but the daemon is not running."
fi

backend_hcl="infra/envs/${env_name}/backend.hcl"
[[ -f "$backend_hcl" ]] || die "${backend_hcl} is missing. Run bash init.sh first."

aws_cli=(aws)
if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws_cli+=(--profile "$AWS_PROFILE")
fi

if ! "${aws_cli[@]}" sts get-caller-identity >/dev/null; then
  die "AWS credentials are not usable. Configure them, then re-run."
fi

account="$("${aws_cli[@]}" sts get-caller-identity --query Account --output text)"

confirm_apply() {
  echo "This applies infra/bootstrap and infra/envs/${env_name} in account ${account}."
  if [[ "$env_name" == "dev" ]]; then
    echo "Dev creates the hello-world site, ECS API, PostgreSQL, OpenSearch, and application S3 bucket."
  fi
  if [[ "$assume_yes" -eq 1 ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    die "Refusing to apply without a terminal. Re-run with --yes."
  fi
  reply=""
  read -r -p "Continue? [y/N] " reply || true
  case "$reply" in
    y|Y|yes|YES) ;;
    *) die "Aborted." ;;
  esac
}

apply_dir() {
  local dir="$1"
  shift
  echo "Applying ${dir}..."
  terraform -chdir="$dir" init -input=false "$@"
  terraform -chdir="$dir" apply -input=false -auto-approve
}

confirm_apply
apply_dir "infra/bootstrap"
apply_dir "infra/envs/${env_name}" -backend-config=backend.hcl -reconfigure

echo "Applied infra/bootstrap and infra/envs/${env_name} in account ${account}."
terraform -chdir="infra/envs/${env_name}" output
