# Local Run Troubleshooting

## Common Startup Issues

- Missing dependencies: run `uv sync --all-extras --all-groups` in `app/`.
- Pending migrations: run `python manage.py migrate`.
- Missing static assets: run relevant static build steps.

## Quick Verification

- `python manage.py check` passes.
- Server starts on expected local host/port.
- Landing page renders without missing asset errors.

## Practical Notes

- Use the project virtual environment before invoking manage.py commands.
- Keep environment variables aligned with local settings files.
