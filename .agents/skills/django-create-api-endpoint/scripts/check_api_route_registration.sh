#!/usr/bin/env bash
set -euo pipefail

# Basic guardrail for API endpoint changes.
# Usage: ./check_api_route_registration.sh <file1> [file2 ...]

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <file1> [file2 ...]" >&2
  exit 1
fi

status=0
has_api_file=0
has_router_file=0

for file in "$@"; do
  case "$file" in
    app/eventyay/api/*)
      has_api_file=1
      ;;
  esac
  case "$file" in
    app/eventyay/api/urls.py|app/eventyay/api/*router*.py)
      has_router_file=1
      ;;
  esac
done

if [[ "$has_api_file" -eq 0 ]]; then
  echo "WARN: no files under app/eventyay/api/ were provided"
  status=2
fi

if [[ "$has_router_file" -eq 0 ]]; then
  echo "WARN: no router/url registration file was provided"
  status=2
fi

if [[ "$status" -eq 0 ]]; then
  echo "OK: API endpoint change includes api path and router/url path."
fi

exit "$status"
