#!/usr/bin/env bash
set -euo pipefail

# Print common top-level project locations used by agents.
cat <<'EOF'
app/eventyay/
app/tests/
doc/
deployment/
.github/instructions/
.agents/skills/
EOF
