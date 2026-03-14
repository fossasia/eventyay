# Skill: Repository Navigation

## Top-level Layout

```
.
├── app/                    # Main Django application
├── deployment/             # Infrastructure and deployment configs
├── doc/                    # Project documentation
├── .github/instructions/   # File-scoped AI coding guidance
├── .agents/skills/         # AI agent skill files (this directory)
├── agents.md               # Canonical AI agent policy
├── docker-compose.yml      # Docker Compose for local/dev environment
├── DEPLOYMENT.md           # Production deployment walkthrough
├── CONTRIBUTING.md         # Contributor guidelines
└── README.rst              # Project overview
```

## Application Root: `app/`

```
app/
├── eventyay/               # Core Django application package
├── tests/                  # Test suite
├── pyproject.toml          # Project metadata and dependencies
└── manage.py               # Django management entry point
```

## Core Application: `app/eventyay/`

| Directory | Purpose |
|---|---|
| `api/` | REST API endpoints (Django REST Framework) |
| `base/` | Shared models (`base/models/`), utilities, middleware, and forms (`base/forms/`) |
| `control/` | Organiser/back-office views, forms, and URLs |
| `presale/` | Attendee-facing (ticket purchase) views and forms |
| `common/` | Cross-cutting helpers shared across modules |
| `config/` | Application configuration and settings |
| `plugins/` | Plugin infrastructure |
| `static/` | Static assets (CSS, JS, images) |
| `jinja-templates/` | Jinja HTML templates |
| `locale/` | Translation files |
| `mail/` | Email rendering and sending |
| `celery.py` / `celery_app.py` | Celery task configuration |

> **Note:** Models, forms, and templates are distributed inside sub-apps
> (e.g. `base/models/`, `control/forms/`, `presale/templates/`), not in
> standalone top-level directories.

## Deployment: `deployment/`

```
deployment/
├── docker-compose.yml      # Production Compose file
├── env.sample              # Sample environment variables
├── env.dev.sample          # Sample dev environment variables
└── nginx/                  # Nginx configuration
```

## Documentation: `doc/`

Contains extended project documentation written in reStructuredText or Markdown.

## Key Lookup Shortcuts

- **Add a model** → `app/eventyay/<sub-app>/models.py` or `app/eventyay/base/models/`
- **Add an API endpoint** → `app/eventyay/api/`
- **Add a form** → `app/eventyay/<sub-app>/forms.py` or `app/eventyay/<sub-app>/forms/`
- **Add a migration** → run `python manage.py makemigrations` from `app/`
- **Add a test** → `app/tests/`
