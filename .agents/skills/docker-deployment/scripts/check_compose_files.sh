#!/usr/bin/env bash
set -euo pipefail

# Verify required compose files exist.
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required=(
  "docker-compose.yml"
  "deployment/docker-compose.yml"
  "deployment/env.sample"
  "deployment/env.dev.sample"
)

for file in "${required[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: missing required file: $file" >&2
    exit 1
  fi
done

echo "OK: compose and env files are present."
