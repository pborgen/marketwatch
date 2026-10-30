#!/usr/bin/env bash
# Remove the local files created by init.sh.
#
#   bash init_cleanup.sh
#
# The AWS CLI, Terraform, and uv stay installed. init.sh installs them only
# when they are missing, and they are shared with the rest of this machine.
# skills-lock.json stays, so skills.sh can install the same set again.
# Terraform state and .terraform directories stay. init.sh does not apply
# infrastructure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

remove_path() {
  local path="$1"
  if [[ -e "$path" || -L "$path" ]]; then
    rm -rf "$path"
    echo "Removed ${path}"
  fi
}

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

echo "Removing agent skills installed by skills.sh..."
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

echo "Removing MCP servers written by mcp.sh..."
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

echo "Removing Terraform backend config written by init.sh..."
remove_path "infra/envs/dev/backend.hcl"
remove_path "infra/envs/prod/backend.hcl"

echo "Cleanup finished."
