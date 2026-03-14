# Skill: Django Backend

## Project Layout

The Django project lives entirely under `app/`.

```
app/
├── eventyay/           # Main package (DJANGO_SETTINGS_MODULE points here)
│   ├── config/         # settings.py and related configuration
│   ├── api/            # DRF viewsets, serializers, routers
│   ├── base/           # Shared models, managers, middleware (includes base/models/, base/forms/)
│   ├── control/        # Organiser back-office views, forms, and URLs
│   ├── presale/        # Attendee-facing views, forms, and URLs
│   ├── common/         # Cross-cutting helpers shared across modules
│   ├── plugins/        # Plugin infrastructure
│   ├── static/         # Static assets (CSS, JS, images)
│   ├── celery.py       # Celery application instance
│   └── celery_app.py   # Celery application instance (alias)
├── tests/              # pytest test suite
└── manage.py
```

> **Note:** Models and forms are distributed inside sub-apps (e.g. `base/models/`,
> `control/forms/`, `presale/forms/`), not in standalone top-level directories.

## Models

- Most models inherit from a base class in `app/eventyay/base/`.
- **Multi-tenancy**: any queryset that crosses event boundaries must be wrapped with `django_scopes.scope(event=event)`.
- Prefer `select_related` / `prefetch_related` to avoid N+1 queries.

## API Endpoints

- Defined in `app/eventyay/api/` using Django REST Framework.
- Routers are registered in `app/eventyay/api/urls.py` (or similar).
- Avoid `SerializerMethodField`; prefer explicit field definitions.

## Forms and Validators

- Form classes live alongside their sub-app (e.g. `app/eventyay/base/forms/`, `app/eventyay/control/forms/`).
- Field-level validation goes in `clean_<field>()` methods.
- Cross-field validation goes in `clean()`.

## Migration Workflow

```bash
# From app/
python manage.py makemigrations
python manage.py migrate
```

Migrations are auto-generated; do not hand-edit them unless absolutely necessary.

## Management Commands

- Defined under `app/eventyay/<sub-app>/management/commands/`.
- Declare parameters explicitly in `handle()` rather than reading from `options` dict.

## Settings

- Base settings are in `app/eventyay/config/settings.py` (or equivalent path).
- Environment-specific overrides come from `.env.dev` (development) or `.env` (production).
- Use `django.conf.settings` in code; never import the settings module directly.

## Running Locally (without Docker)

```bash
cd app
uv sync --all-extras --all-groups
. .venv/bin/activate
python manage.py migrate
python manage.py runserver
```
