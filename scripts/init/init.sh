#!/usr/bin/env bash
# Prepare this repo to deploy to AWS with Terraform.
#
#   AWS_PROFILE=dev AWS_REGION=us-east-1 bash init.sh
#
# AWS_PROFILE is optional. AWS_REGION falls back to the AWS CLI config, then us-east-1.
# It is used for the AWS CLI and Cursor MCP config. The state bucket region is
# aws_region in infra/bootstrap/terraform.tfvars.
#
# The script installs agent skills (scripts/init/skills.sh), the Strands runtime,
# Cursor MCP servers including strands-agents-mcp-server (scripts/init/mcp.sh),
# and Terraform. It verifies AWS credentials, then writes infra/envs/*/backend.hcl.
# It does not apply infrastructure. Deploy this application's stacks with:
#
#   bash init-market-watch.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

die() {
  echo "error: $*" >&2
  exit 1
}

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python 3.10 or newer is required."

command -v node >/dev/null 2>&1 || die "Node.js 18 or newer is required."
command -v npm >/dev/null 2>&1 || die "npm is required (it ships with Node.js)."

node_major="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$node_major" -ge 18 ]] || die "Node.js 18 or newer is required (found $(node -v))."

bash "$ROOT/scripts/init/skills.sh"

echo "Installing the Strands runtime..."
STRANDS_DIR="vendor/sample-strands-agents-agentskills"
if [[ ! -d "$STRANDS_DIR/.git" ]]; then
  mkdir -p vendor
  git clone --depth 1 \
    https://github.com/aws-samples/sample-strands-agents-agentskills.git \
    "$STRANDS_DIR"
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e "$STRANDS_DIR" -e "$ROOT/packages/datafeed" -e "$ROOT/packages/envfile" boto3

if ! command -v aws >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing the AWS CLI..."
    brew install awscli
  else
    die "Install the AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  fi
fi

if ! command -v terraform >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing Terraform..."
    brew tap hashicorp/tap
    brew install hashicorp/tap/terraform
  else
    die "Install Terraform 1.10 or newer: https://developer.hashicorp.com/terraform/install"
  fi
fi

terraform version -json | python3 -c '
import json, sys
version = json.load(sys.stdin)["terraform_version"].split("-", 1)[0]
parts = [int(p) for p in version.split(".")[:2]]
if parts < [1, 10]:
    raise SystemExit(f"Terraform 1.10 or newer is required (found {version}).")
'

AWS_REGION_RESOLVED="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ -z "$AWS_REGION_RESOLVED" ]]; then
  AWS_REGION_RESOLVED="$(aws configure get region 2>/dev/null || true)"
fi
AWS_REGION_RESOLVED="${AWS_REGION_RESOLVED:-us-east-1}"
export AWS_REGION="$AWS_REGION_RESOLVED"
export AWS_DEFAULT_REGION="$AWS_REGION_RESOLVED"

bash "$ROOT/scripts/init/mcp.sh"

aws_cli=(aws)
if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws_cli+=(--profile "$AWS_PROFILE")
fi

if ! "${aws_cli[@]}" sts get-caller-identity >/dev/null; then
  cat <<EOF >&2
AWS credentials are not usable yet, so infra/envs/*/backend.hcl was not written.
Local tools are in place. Configure access, then re-run:

  aws configure
  # or, for IAM Identity Center:
  aws configure sso
  aws sso login

EOF
  exit 1
fi

account="$("${aws_cli[@]}" sts get-caller-identity --query Account --output text)"

python3 "$ROOT/scripts/init/write_backend_hcl.py" "$ROOT" "$account"

cat <<EOF
Account ${account}, CLI region ${AWS_REGION_RESOLVED}.

Deploy this application's infrastructure:

  bash init-market-watch.sh
  bash init-market-watch.sh prod
EOF
