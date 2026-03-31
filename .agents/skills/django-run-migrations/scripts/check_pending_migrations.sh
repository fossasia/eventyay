#!/usr/bin/env bash
set -euo pipefail

# Fail when model changes require migrations.
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root/app"

python manage.py makemigrations --check --dry-run

echo "OK: no pending migrations detected."
