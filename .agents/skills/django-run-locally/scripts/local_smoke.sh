#!/usr/bin/env bash
set -euo pipefail

# Run minimal local Django checks from app/.
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root/app"

python manage.py check
python manage.py showmigrations --plan >/dev/null

echo "OK: local Django smoke checks passed."
