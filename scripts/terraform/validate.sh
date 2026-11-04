#!/usr/bin/env bash
# Validate every Terraform root. init uses -backend=false, so this does not
# need the state bucket or AWS credentials. The lock file selects providers.
#
#   bash scripts/terraform/validate.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is not installed. Run: bash init.sh" >&2
  exit 1
fi

roots=(
  infra/bootstrap
  infra/envs/dev
  infra/envs/prod
)

for dir in "${roots[@]}"; do
  echo "terraform validate ${dir}"
  terraform -chdir="$dir" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="$dir" validate
done
