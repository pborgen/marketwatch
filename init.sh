#!/usr/bin/env bash
# Entry point for scripts/init/init.sh.
#
#   AWS_PROFILE=dev AWS_REGION=us-east-1 bash init.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/init/init.sh" "$@"
