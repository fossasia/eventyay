# PR Readiness Guide

## Before Opening a PR

- Rebase or merge latest `dev` if needed.
- Run relevant tests for touched areas.
- Confirm no debug logs or temporary files are included.
- Check docs when behavior or workflow changed.

## PR Description Should Include

- What changed
- Why it changed
- How it was tested
- Any known risks or follow-up items

## During Review

- Reply to each substantive comment.
- Prefer small follow-up commits over force-push rewrites.
- Re-run targeted tests after feedback changes.

## Merge Readiness

- CI checks pass
- Required approvals are present
- No unresolved blocking comments
