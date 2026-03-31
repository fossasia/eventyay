#!/usr/bin/env bash
set -euo pipefail

# Quick guardrail: show changed files and fail if there are too many.
# Usage: ./check_pr_scope.sh [max_files]

max_files="${1:-40}"
count="$( (git diff --name-only HEAD~1..HEAD 2>/dev/null || true) | wc -l | tr -d ' ' )"

if [[ "$count" -eq 0 ]]; then
  echo "No changed files detected in HEAD~1..HEAD."
  exit 0
fi

echo "Changed files in last commit: $count"
if [[ "$count" -gt "$max_files" ]]; then
  echo "WARN: change set is larger than recommended threshold ($max_files files)."
  exit 2
fi

echo "OK: scope is within threshold."
