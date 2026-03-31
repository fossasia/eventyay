#!/usr/bin/env bash
set -euo pipefail

# Validate model file placement.
# Usage: ./check_model_location.sh <file1> [file2 ...]

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <file1> [file2 ...]" >&2
  exit 1
fi

status=0
for file in "$@"; do
  case "$file" in
    app/eventyay/*/models.py|app/eventyay/*/models/*.py)
      echo "OK: $file"
      ;;
    *)
      echo "WARN: $file is outside expected models locations"
      status=2
      ;;
  esac
done

exit "$status"
