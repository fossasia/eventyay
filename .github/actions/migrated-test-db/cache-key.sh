#!/usr/bin/env bash
# Prints the hash used in the migrated test database cache key.
#
# Django records applied migrations by app and file name, so the key covers each
# migration file's path as well as its contents: renaming a migration must build
# a new dump even when its bytes are unchanged. app/uv.lock covers migrations
# that come from dependencies such as the plugins.
#
# Usage: cache-key.sh [repository root]
set -euo pipefail
cd "${1:-.}"
{
  find app/eventyay -type f -path '*/migrations/*.py' -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 -r sha256sum
  sha256sum app/uv.lock
} | sha256sum | cut -d' ' -f1
