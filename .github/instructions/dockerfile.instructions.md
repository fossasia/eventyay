---
applyTo:
  - '**/Dockerfile*'
  - '**/docker-compose*.yml'
---
# Docker and Container Reference

This document covers Docker Compose usage, container services, environment variables, and the development workflow for Eventyay.

**Core Architecture Principle:**
- **Development (`docker-compose.yml`)**: Builds directly from `app/Dockerfile`. The `web` container serves static assets directly via Django.
- **Production (`deployment/docker-compose.yml`)**: Uses a pre-built image (`eventyay/eventyay-next:${TAG}`) rather than building it locally. This image is built from `app/Dockerfile.prod` via CI/CD pipelines. Static assets are pre-built. In production, Nginx is typically configured at the host level (outside this Compose stack) to reverse-proxy requests to the Gunicorn application server.

For the full production deployment walkthrough including Nginx, SSL, and backups, see [`DEPLOYMENT.md`](../../DEPLOYMENT.md).

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
| `EVY_SECRET_KEY` | Django secret key (keep it secret) |
| `EVY_POSTGRES_DB` | PostgreSQL database name used by the Django app |
| `EVY_POSTGRES_USER` | PostgreSQL username used by the Django app |
| `EVY_POSTGRES_PASSWORD` | PostgreSQL password used by the Django app |
| `POSTGRES_DB` | PostgreSQL database name used by the database container |
| `POSTGRES_USER` | PostgreSQL username used by the database container |
| `POSTGRES_PASSWORD` | PostgreSQL password used by the database container |
| `EVY_REDIS_URL` | Redis connection URL |
| `EVY_SITE_URL` | Public site URL, e.g. `https://<SERVER_NAME>` |
| `EVY_ALLOWED_HOSTS` | Django `ALLOWED_HOSTS`, e.g. `<SERVER_NAME>` |

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
docker compose exec web python manage.py create_admin_user
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

The production stack uses Gunicorn (instead of Django's dev server) behind a host-level Nginx reverse proxy outside the Compose stack.

```bash
# On the production server
cd /home/$USER/$DEPLOYMENT_NAME/eventyay
# Use the production compose file from the cloned repository
docker compose -f deployment/docker-compose.yml up -d
```

If your server setup follows a top-level compose symlink (as shown in `DEPLOYMENT.md`),
run from `/home/$USER/$DEPLOYMENT_NAME` with that symlinked compose file instead.

Refer to [`DEPLOYMENT.md`](../../DEPLOYMENT.md) for the complete step-by-step guide including SSL setup with Certbot.

---

## Notes

- The `web` and `worker` services share the exact same Docker image built from `app/Dockerfile`.
- Volume mounts in the development stack allow live code reloading without rebuilding the image.
