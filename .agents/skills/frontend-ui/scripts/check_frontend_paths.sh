#!/usr/bin/env bash
set -euo pipefail

# Verify a list of changed files maps to expected frontend locations.
# Usage: ./check_frontend_paths.sh <file1> [file2 ...]

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <file1> [file2 ...]" >&2
  exit 1
fi

status=0
for file in "$@"; do
  case "$file" in
    app/eventyay/static/*|app/eventyay/webapp/*|app/eventyay/*/templates/*)
      echo "OK: $file"
      ;;
    *)
      echo "WARN: $file is outside common frontend paths"
      status=2
      ;;
  esac
done

exit "$status"
