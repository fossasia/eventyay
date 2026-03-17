# Django Backend Architecture Context

## Project Layout

The Django project lives entirely under `app/`. The main package is `eventyay` (`DJANGO_SETTINGS_MODULE` points here).

```
app/
├── eventyay/           # Main package
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

> **Note:** Models and forms are distributed inside sub-apps (e.g., `base/models/`, `control/forms/`, `presale/forms/`), not in standalone top-level directories. Most models inherit from a base class in `app/eventyay/base/`.

## Settings
- Base settings are in `app/eventyay/config/settings.py` (check `BaseSettings` class).
- Environment-specific overrides come from `.toml` files (`eventyay.development.toml`, `eventyay.production.toml`) and `eventyay.local.toml`.
- Running environment is selected via the `EVY_RUNNING_ENVIRONMENT` environment variable.
