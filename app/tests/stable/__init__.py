# tests/stable — curated integration tests that run in CI
#
# This package contains a subset of the full test suite that passes reliably
# against the current codebase. It is the scope executed by the CI workflow
# (video-backend-ci.yml) via `pytest tests/stable`.
#
# Why not the full tests/ tree?
# The broader tests/ directory includes legacy test suites inherited from the
# project's history (pretix, pretalx, venueless). Many of those contain
# outdated imports and assumptions that do not match the unified eventyay layout.
# Running them all in CI would produce a high false-failure rate that masks real
# regressions.
#
# Path forward (tracked here so this does not become permanent technical debt):
#   1. Fix legacy tests incrementally, module by module.
#   2. Once a module's tests are green, move or symlink them into this package
#      (or remove this restriction and widen the pytest path in the workflow).
#   3. Tests that cannot reasonably be fixed should be explicitly quarantined
#      using a `@pytest.mark.legacy` marker and collected in a separate
#      non-blocking CI job.
