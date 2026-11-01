#!/usr/bin/env bash
# Remove the local files created by scripts/init/init.sh.
#
#   bash init_cleanup.sh
#   bash init_cleanup.sh --aws
#
# The AWS CLI, Terraform, and uv stay installed. scripts/init/init.sh installs
# them only when they are missing, and they are shared with the rest of this
# machine. skills-lock.json stays, so scripts/init/skills.sh can install the same
# set again.
#
# Without --aws, Terraform state and .terraform directories stay.
# scripts/init/init.sh does not apply infrastructure.
#
# --aws destroys resources managed by infra/envs, deletes the bootstrap state
# bucket, and removes local Terraform state. The bucket is protected with
# prevent_destroy, so this deletes it with the AWS CLI after checking the name.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

destroy_aws=0
assume_yes=0

usage() {
  cat <<'EOF'
Usage: bash init_cleanup.sh [--aws] [--yes]

  --aws  Destroy AWS resources managed by this repo and remove local Terraform state.
  --yes  Skip the confirmation prompt for --aws.
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --aws) destroy_aws=1 ;;
    --yes) assume_yes=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
  shift
done

if [[ "$assume_yes" -eq 1 && "$destroy_aws" -eq 0 ]]; then
  die "--yes is only valid with --aws."
fi

remove_path() {
  local path="$1"
  if [[ -e "$path" || -L "$path" ]]; then
    rm -rf "$path"
    echo "Removed ${path}"
  fi
}

confirm_aws_destroy() {
  echo "This destroys resources managed by infra/envs, deletes the Terraform state bucket, and removes local Terraform state."
  if [[ "$assume_yes" -eq 1 ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    die "Refusing to destroy AWS resources without a terminal. Re-run with --aws --yes."
  fi
  reply=""
  read -r -p "Continue? [y/N] " reply || true
  case "$reply" in
    y|Y|yes|YES) ;;
    *) die "Aborted." ;;
  esac
}

destroy_env() {
  local env="$1"
  local dir="infra/envs/${env}"
  if [[ ! -d "$dir/.terraform" ]]; then
    echo "Skipping infra/envs/${env}; it has not been initialized."
    return 0
  fi
  echo "Destroying resources in infra/envs/${env}..."
  terraform -chdir="$dir" destroy -input=false -auto-approve
}

remove_terraform_local() {
  echo "Removing local Terraform state..."
  remove_path "infra/bootstrap/.terraform"
  remove_path "infra/bootstrap/terraform.tfstate"
  remove_path "infra/bootstrap/terraform.tfstate.backup"
  remove_path "infra/bootstrap/.terraform.tfstate.lock.info"
  local env
  for env in dev prod; do
    remove_path "infra/envs/${env}/.terraform"
    remove_path "infra/envs/${env}/terraform.tfstate"
    remove_path "infra/envs/${env}/terraform.tfstate.backup"
    remove_path "infra/envs/${env}/.terraform.tfstate.lock.info"
  done
}

if [[ "$destroy_aws" -eq 1 ]]; then
  command -v terraform >/dev/null 2>&1 || die "Terraform is required for --aws."
  command -v aws >/dev/null 2>&1 || die "The AWS CLI is required for --aws."
  confirm_aws_destroy
  destroy_env prod
  destroy_env dev
  python3 "$ROOT/scripts/init/delete_state_bucket.py" "$ROOT"
  remove_terraform_local
fi

skills=(
  agentcore-browser-web-scraping
  agentcore-mcp-oauth-facade
  agentic-responsible-ai-assessment
  api-gateway-authorizer-security
  aws-agentic-ai
  aws-cdk-development
  aws-cost-operations
  aws-mcp-setup
  cost-estimator
  create-install-scripts
  end-to-end-testing
  security-scan
  strands-context-manager
  skill-creator
)

echo "Removing agent skills installed by scripts/init/skills.sh..."
for skill in "${skills[@]}"; do
  remove_path ".agents/skills/${skill}"
done
if rmdir .agents/skills 2>/dev/null; then
  echo "Removed .agents/skills"
fi
if rmdir .agents 2>/dev/null; then
  echo "Removed .agents"
fi

echo "Removing the Strands checkout and virtualenv..."
remove_path "vendor/sample-strands-agents-agentskills"
if rmdir vendor 2>/dev/null; then
  echo "Removed vendor"
fi
remove_path ".venv"

echo "Removing MCP servers written by scripts/init/mcp.sh..."
python3 - "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) / ".cursor" / "mcp.json"
if not path.exists():
    raise SystemExit(0)

data = json.loads(path.read_text())
servers = data.get("mcpServers", {})
removed = [
    name
    for name in ("aws-mcp", "awsdocs", "strands-agents")
    if name in servers
]
for name in removed:
    del servers[name]

if not servers:
    path.unlink()
    print("Removed .cursor/mcp.json")
elif removed:
    data["mcpServers"] = servers
    path.write_text(json.dumps(data, indent=2) + "\n")
    print("Removed " + ", ".join(removed) + " from .cursor/mcp.json")
PY

echo "Removing Terraform backend config written by scripts/init/init.sh..."
remove_path "infra/envs/dev/backend.hcl"
remove_path "infra/envs/prod/backend.hcl"

echo "Cleanup finished."
