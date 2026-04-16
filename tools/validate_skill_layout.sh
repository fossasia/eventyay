#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

skills_root=".agents/skills"
required_dirs=(references assets)
optional_dirs=(tests)

if [[ ! -d "$skills_root" ]]; then
  echo "ERROR: missing $skills_root" >&2
  exit 1
fi

status=0

for skill_dir in "$skills_root"/*; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"

  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "ERROR: $skill_name missing SKILL.md"
    status=1
  fi

  for d in "${required_dirs[@]}"; do
    path="$skill_dir/$d"
    if [[ ! -d "$path" ]]; then
      echo "ERROR: $skill_name missing $d/"
      status=1
      continue
    fi

    if ! find "$path" -mindepth 1 -type f | read -r _; then
      echo "ERROR: $skill_name has empty $d/"
      status=1
    fi
  done

  for d in "${optional_dirs[@]}"; do
    path="$skill_dir/$d"
    if [[ -d "$path" ]] && ! find "$path" -mindepth 1 -type f | read -r _; then
      echo "ERROR: $skill_name has empty optional $d/"
      status=1
    fi
  done
done

if [[ "$status" -eq 0 ]]; then
  echo "OK: all skills have required files/directories and valid optional directories."
fi

exit "$status"
