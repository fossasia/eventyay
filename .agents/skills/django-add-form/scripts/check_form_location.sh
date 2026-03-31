#!/usr/bin/env bash
set -euo pipefail

# Validate that form files are placed in expected Django app locations.
# Usage: ./check_form_location.sh <file1> [file2 ...]

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <file1> [file2 ...]" >&2
  exit 1
fi

status=0
for file in "$@"; do
  case "$file" in
    app/eventyay/*/forms.py|app/eventyay/*/forms/*.py)
      echo "OK: $file"
      ;;
    *)
      echo "WARN: $file is outside expected forms locations"
      status=2
      ;;
  esac
done

exit "$status"
