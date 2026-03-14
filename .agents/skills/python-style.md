# Skill: Python Style

Full Python coding standards are defined in:

**`.github/instructions/python.instructions.md`**

Read that file first. This skill provides a concise summary of the most important expectations.

## Key Expectations

### Imports
Place all imports at the top of the file. Use local imports only to break circular dependencies.

### Namespaces
Use `eventyay.*` for all new imports. Do not introduce new `pretix.*`, `pretalx.*`, or `venueless.*` namespaces.

### Logging
- Use `%s`-style interpolation: `logger.info('User %s logged in', username)`.
- Never use f-strings to build log messages.
- Catch specific exceptions, not `Exception` or `BaseException`.
- Do not wrap exception objects in `str()` when passing to a logger.
- When using `logger.exception()`, omit the exception object from the message — the traceback is included automatically.

### Datetime Formatting
Prefer f-string format specifiers: `f"{dt:%Y-%m-%d %H:%M:%S}"` over `dt.strftime(...)`.

### Function Design
- Avoid underscore-prefixed private functions unless there is a clear reason.
- Static-like logic (no `self`) belongs in module-level functions, not class methods.

### Type Annotations
New functions should have parameter and return-type annotations where practical. Avoid `Any`; use `TypedDict`, `NamedTuple`, or `dataclass` for structured return values.

### Data Validation
Validate data from external sources (HTTP responses, JSON fields, Redis) with DRF serializers or Pydantic models before use.

## Runtime Baseline

Python **3.12** (Ubuntu 24.04 LTS). No backward compatibility with older versions is required.
