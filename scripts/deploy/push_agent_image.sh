#!/usr/bin/env bash
# Build an agent image and push it to ECR.
# Called from the AgentCore Terraform module during apply.
# AGENT_DOCKERFILE is relative to the repo root. The demo agent is the default.
# The image must be linux/arm64. AgentCore rejects other architectures.
set -euo pipefail

: "${ECR_REPOSITORY_URL:?}"
: "${AWS_REGION:?}"
: "${IMAGE_TAG:?}"
: "${DOCKER_PLATFORM:?}"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
registry="${ECR_REPOSITORY_URL%%/*}"
image="${ECR_REPOSITORY_URL}:${IMAGE_TAG}"

# A private Docker config avoids the macOS keychain. Two publishes run at once
# during apply, and the keychain rejects the second write.
docker_config="$(mktemp -d)"
trap 'rm -rf "$docker_config"' EXIT
printf '%s\n' '{"auths":{}}' > "${docker_config}/config.json"
export DOCKER_CONFIG="$docker_config"

dockerfile="${AGENT_DOCKERFILE:-apps/agents/demo/Dockerfile}"

echo "Publishing ${image} (${DOCKER_PLATFORM}) from ${dockerfile}..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$registry"
docker build --platform "$DOCKER_PLATFORM" \
  -f "$root/$dockerfile" \
  -t "$image" \
  "$root"
docker push "$image"
