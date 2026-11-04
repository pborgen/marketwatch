#!/usr/bin/env bash
# Build apps/api and push it to the dev ECR repository.
# Called from the ECS Terraform module during apply.
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

echo "Publishing ${image} (${DOCKER_PLATFORM})..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$registry"
docker build --platform "$DOCKER_PLATFORM" -f "$root/apps/api/Dockerfile" -t "$image" "$root"
docker push "$image"
