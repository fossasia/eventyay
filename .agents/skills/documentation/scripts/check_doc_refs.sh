#!/usr/bin/env bash
set -euo pipefail

# Check that common docs referenced by skills exist.
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required=(
  "README.rst"
  "CONTRIBUTING.md"
  "DEPLOYMENT.md"
  "doc/index.rst"
)

for file in "${required[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: missing documentation file: $file" >&2
    exit 1
  fi
done

echo "OK: key documentation references exist."
