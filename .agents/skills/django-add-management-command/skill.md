---
name: django-add-management-command
description: Steps for defining a custom Django administration/management command
---

## When to use

Use this skill when creating backend `manage.py` system or background utilities and scripts.

## Steps

1. Create a Python script representing the new command inside the required sub-app framework structured logically under `app/eventyay/<sub-app>/management/commands/`.
2. Ensure the command class inherits from Django's generic `BaseCommand`.
3. Explicitly declare any accepted parameters internally and safely within the core `handle()` workflow.

## Validation

1. Run `python manage.py help <command_name>` natively from `app/` to ensure it is registered to the engine and returns expected arguments.

## Gotchas

- **Argument Parsing Error:** Avoid reading directly from the `options` dictionary for parameters randomly. Always explicitly resolve and declare required parameters sequentially inside `handle()` context logic.
