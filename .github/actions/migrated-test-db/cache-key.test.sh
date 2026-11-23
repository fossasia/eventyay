#!/usr/bin/env bash
# Checks that cache-key.sh changes the key when a migration is renamed, added or
# edited, or when app/uv.lock changes, and keeps it stable otherwise.
set -euo pipefail
key_script="$(cd "$(dirname "$0")" && pwd)/cache-key.sh"
root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT

mkdir -p "$root/app/eventyay/base/migrations"
echo 'operations = []' > "$root/app/eventyay/base/migrations/0001_initial.py"
echo 'lock' > "$root/app/uv.lock"

fail() { echo "FAIL: $1"; exit 1; }
key() { "$key_script" "$root"; }

base=$(key)
[ "$base" = "$(key)" ] || fail "key is not stable"

mv "$root/app/eventyay/base/migrations/0001_initial.py" "$root/app/eventyay/base/migrations/0001_renamed.py"
renamed=$(key)
[ "$renamed" != "$base" ] || fail "renaming a migration with the same bytes kept the key"

echo 'operations = []' > "$root/app/eventyay/base/migrations/0002_more.py"
added=$(key)
[ "$added" != "$renamed" ] || fail "adding a migration kept the key"

echo 'operations = [1]' > "$root/app/eventyay/base/migrations/0002_more.py"
edited=$(key)
[ "$edited" != "$added" ] || fail "editing a migration kept the key"

echo 'lock2' > "$root/app/uv.lock"
[ "$(key)" != "$edited" ] || fail "changing app/uv.lock kept the key"

mkdir -p "$root/app/eventyay/base/templates"
echo 'x' > "$root/app/eventyay/base/templates/page.py"
locked=$(key)
echo 'y' > "$root/app/eventyay/base/templates/page.py"
[ "$(key)" = "$locked" ] || fail "a file outside migrations changed the key"

echo "cache-key.sh: all checks passed"
