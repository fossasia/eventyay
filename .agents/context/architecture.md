# Django Backend Architecture Context

## Core Structure & Philosophy

The Django project lives entirely under `app/`. The project has evolved from a legacy structure to the unified `eventyay` (ENext) application.

- The primary package is `eventyay` (`DJANGO_SETTINGS_MODULE` points here).
- You will see legacy directories (like `src/`, `talk/`, `video/`) in older branches, but they are historical. All active product code lives strictly inside `app/eventyay/`.

## Directory Map (`app/eventyay/`, selected modules)

```text
app/
├── eventyay/           # Main unifying package
│   ├── agenda/         # Agenda and timetable domain logic
│   ├── cfp/            # Call-for-proposals workflow and review flow
│   ├── config/         # System configuration and settings.py files
│   ├── api/            # DRF viewsets, serializers, routers
│   ├── base/           # Core shared models, managers, forms, and middleware
│   ├── control/        # Organiser back-office (management UI, forms, urls)
│   ├── event/          # Event domain models and business logic
│   ├── orga/           # Organiser-specific UI and domain workflows
│   ├── person/         # Person/profile-related models and views
│   ├── presale/        # Attendee-facing (ticket purchase, public pages, urls)
│   ├── schedule/       # Schedule generation, rendering, and exports
│   ├── submission/     # Submission lifecycle, review, and talk handling
│   ├── eventyay_common/  # Modern shared UI components and base templates
│   ├── webapp/         # Modern Vue 3 bundled front-end applications
│   ├── static/         # Legacy/Django-served static assets (CSS, images)
│   ├── celery.py       # Celery task application configuration
│   └── plugins/        # Extendible plugin architecture definitions
├── tests/              # Pytest testing suite
└── manage.py
```

This map is intentionally non-exhaustive; use it as a navigation guide for major modules.

> **Crucial Rule on Sub-apps:** Models and forms are distributed *inside* their respective domain sub-apps to guarantee domain-driven design separation. 
> - Examples: `base/models/`, `control/forms/`, `presale/forms/` 
> - **Do NOT** place models or forms directly in a new root-level standalone directory. 
> - By standard convention, most system models inherit from a core database class located within `app/eventyay/base/`.

## System Settings Layer

Configuration is strictly divided between base settings and environment-specific overrides:

- **Base defaults:** Handled dynamically via `app/eventyay/config/settings.py` (review the `BaseSettings` setup class).
- **Environment Overrides:** Configuration is TOML-based (`eventyay.development.toml`, `eventyay.production.toml`) plus an optional `eventyay.local.toml` for strict local machine overrides.
- **Execution Context:** The active mode executes according to the `EVY_RUNNING_ENVIRONMENT` OS environment variable which defaults depending on context (`development`, `production`, etc.).
