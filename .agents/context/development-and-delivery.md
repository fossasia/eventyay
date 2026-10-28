# Development and delivery context

## Authoritative setup files

Read `README.rst`, `CONTRIBUTING.md`, `app/pyproject.toml`, and the relevant workflow
before setup. Python 3.12 is the runtime baseline. PostgreSQL and Redis support
the Django/Celery stack; frontend builds also need Node/npm and native packages
listed in `deb-packages.txt`.

`app/eventyay/config/settings.py` and the environment TOML files under
`app/eventyay/config/` define configuration. Use the sample environment files in
`deployment/` rather than copying credentials from an existing installation.

## Local Python development

From the core repository root:

```sh
cd app
uv sync --all-extras --all-groups
. .venv/bin/activate
# Optional: override packaged dependencies with existing local checkouts.
uv pip install --python .venv/bin/python -e ../plugins/eventyay-business -e ../plugins/eventyay-stripe
python manage.py migrate
python manage.py runserver
```

Configure local PostgreSQL/Redis first using the README. In separate terminals,
activate the same environment and start the workers/beat required by your task.
Use `make staticfiles` or `make production` from `app/` for assets. Compile plugin
translations with `make` from the respective plugin root. Restart Django and
Celery after installation or registration changes.

The editable paths above assume `core/plugins/<repository>`; sibling checkouts
need different paths. A later `uv sync` may restore locked dependencies, so
reinstall editable overrides and verify imports after syncing:

```sh
python -c 'import eventyay_business, eventyay_stripe; print(eventyay_business.__file__); print(eventyay_stripe.__file__)'
```

## Containers and production

`docker-compose.yml` is the development stack. It mounts `./plugins` at
`/usr/src/plugins`. `app/entrypoint.sh` installs local plugins in development when
`EVY_PLUGIN_DEV_MODE` (fallback `PLUGIN_DEV_MODE`) enables it, using installation
stamps. The web process performs initialization including migrations; Celery
processes skip web-only initialization. Confirm installation in workers as well
as web when investigating different behavior between requests and tasks.

`deployment/docker-compose.yml`, `app/Dockerfile.prod`, and
`app/entrypoint.prod.sh` describe production. Production builds use the lockfile;
the Dockerfile retargets plugin sources only for `BUILD_MODE=dev`. Staging
uses the non-dev branch with locked production sources. Inspect build arguments
before assuming a container contains the latest plugin branch.

`.github/workflows/update-plugin-pins.yml` and
`.github/workflows/plugin-dispatch-receiver.yml` maintain integration updates.
Plugin repositories have notification workflows. Documentation-only changes do
not require a dependency bump or deployment. Code changes may require a separate
core lock update after plugin changes merge.

## Verification

From `app/`, activate `.venv` and run `pytest tests/<affected-area>` with test
configuration and a disposable PostgreSQL database. `.github/workflows/video-backend-ci.yml`
is the authority for app backend CI service settings and flags on `dev`; its
`pytest-integration` job provides PostgreSQL and Redis. The older `tests.yml`
workflow targets legacy branches and the absent `src/` layout. Do not reuse a production
database for tests or migrations.

Plugin CI clones core `dev`, installs the plugin into core's environment, and
runs tests from the plugin root. Match that installation order and explicitly
select `DJANGO_SETTINGS_MODULE=eventyay.config.settings`; Business's standalone
`setup.cfg` default differs from CI. Each plugin's context describes its commands.

For agent-context-only changes, check paths, Markdown links, skill frontmatter,
`git diff --check`, and package manifests where applicable. These Markdown files
are outside the Sphinx `doc/` tree; no application test run establishes their
accuracy. Record source inspection separately from runtime tests. Never claim a
live checkout/webhook/payment was tested merely because documentation checks pass.
