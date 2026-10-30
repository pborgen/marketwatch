#!/usr/bin/env bash
# Write .cursor/mcp.json for the AWS and Strands MCP servers.
#
#   AWS_PROFILE=dev AWS_REGION=us-east-1 bash scripts/init/mcp.sh
#
# AWS_PROFILE is optional. AWS_REGION falls back to AWS_DEFAULT_REGION, then the
# AWS CLI config, then us-east-1. Existing MCP servers in .cursor/mcp.json are kept.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

die() {
  echo "error: $*" >&2
  exit 1
}

if ! command -v uvx >/dev/null 2>&1; then
  echo "Installing uv (provides uvx for AWS MCP servers)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi
command -v uvx >/dev/null 2>&1 || die "uvx is not on PATH after installing uv."

AWS_REGION_RESOLVED="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
if [[ -z "$AWS_REGION_RESOLVED" ]]; then
  AWS_REGION_RESOLVED="$(aws configure get region 2>/dev/null || true)"
fi
AWS_REGION_RESOLVED="${AWS_REGION_RESOLVED:-us-east-1}"

echo "Writing Cursor MCP config..."
python3 "$ROOT/scripts/init/write_mcp_config.py" \
  "$ROOT" \
  "$(command -v uvx)" \
  "$AWS_REGION_RESOLVED" \
  "${AWS_PROFILE:-}"
