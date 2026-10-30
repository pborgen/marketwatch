#!/usr/bin/env bash
# Install the agent skills this project uses into .agents/skills/ for Cursor.
#
#   bash scripts/init/skills.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

die() {
  echo "error: $*" >&2
  exit 1
}

command -v node >/dev/null 2>&1 || die "Node.js 18 or newer is required."
command -v npm >/dev/null 2>&1 || die "npm is required (it ships with Node.js)."

node_major="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$node_major" -ge 18 ]] || die "Node.js 18 or newer is required (found $(node -v))."

echo "Installing agent skills for Cursor..."
npx skills add https://github.com/aws-samples/sample-agent-skills-for-builders \
  --skill \
    agentcore-browser-web-scraping \
    agentcore-mcp-oauth-facade \
    agentic-responsible-ai-assessment \
    api-gateway-authorizer-security \
    aws-agentic-ai \
    aws-cdk-development \
    aws-cost-operations \
    aws-mcp-setup \
    cost-estimator \
    create-install-scripts \
    end-to-end-testing \
    security-scan \
    strands-context-manager \
  -a cursor \
  -y

npx skills add https://github.com/aws-samples/sample-strands-agents-agentskills \
  --skill skill-creator \
  -a cursor \
  -y
