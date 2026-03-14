# Docker and Container Reference

This document covers Docker Compose usage, container services, environment variables, and the development workflow for Eventyay.

For the full production deployment walkthrough (Nginx, SSL, backups), see [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Development / local stack |
| `deployment/docker-compose.yml` | Production stack |
| `deployment/env.dev.sample` | Sample development environment variables |
| `deployment/env.sample` | Sample production environment variables |
| `deployment/nginx/` | Nginx reverse-proxy configuration |

---

## Services

### Development stack (`docker-compose.yml`)

| Service | Container name | Port | Description |
|---|---|---|---|
| `web` | `eventyay-next-web` | 8000 | Django development server |
| `worker` | `eventyay-next-worker` | — | Celery task worker |
| `redis` | `eventyay-next-redis` | — | Message broker and cache |
| `db` | `eventyay-next-db` | — | PostgreSQL 15 database |

---

## Environment Variables

Copy the sample file and edit it before starting the stack:

```bash
cp deployment/env.dev.sample .env.dev
```

Key variables to configure:

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key (keep it secret) |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `REDIS_URL` | Redis connection URL |
| `SERVER_NAME` | Hostname (production only) |

See `deployment/env.sample` for a complete annotated list of production variables.

---

## Development Workflow

### Start the stack

```bash
# Build images (first time or after Dockerfile changes)
docker compose up --build

# Start in the background
docker compose up -d --build
```

### View logs

```bash
docker compose logs -f web
docker compose logs -f worker
```

### Run management commands

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
```

### Stop the stack

```bash
docker compose down
```

### Rebuild a single service

```bash
docker compose up --build web
```

---

## Production Workflow

The production stack uses Gunicorn (instead of Django's dev server) behind an Nginx reverse proxy.

```bash
# On the production server
cd /home/$USER/$DEPLOYMENT_NAME
docker compose -f deployment/docker-compose.yml up -d
```

Refer to [`DEPLOYMENT.md`](DEPLOYMENT.md) for the complete step-by-step guide including SSL setup with certbot.

---

## Notes

- Static files are pre-built and served by Nginx in production. In development, Django serves them directly.
- The `web` and `worker` services share the same Docker image built from `app/Dockerfile`.
- Volume mounts in the development stack allow live code reloading without rebuilding the image.
