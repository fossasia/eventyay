# Skill: Docker Deployment

## Key Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | Development / local Compose stack |
| `deployment/docker-compose.yml` | Production Compose stack |
| `deployment/env.sample` | Sample production environment variables |
| `deployment/env.dev.sample` | Sample development environment variables |
| `deployment/nginx/` | Nginx reverse-proxy configuration |
| `DEPLOYMENT.md` | Step-by-step production deployment guide |

## Services (Development Stack)

| Service | Image / Build | Role |
|---|---|---|
| `web` | `./app` (Dockerfile) | Django dev server on port 8000 |
| `worker` | `./app` (Dockerfile) | Celery task worker |
| `redis` | `redis:latest` | Message broker and cache |
| `db` | `postgres:15` | PostgreSQL database |

## Building and Running (Development)

```bash
# Copy and edit environment variables
cp deployment/env.dev.sample .env.dev

# Build images and start all services
docker compose up --build

# Run with detached containers
docker compose up -d --build

# View logs
docker compose logs -f web
docker compose logs -f worker

# Stop all services
docker compose down
```

## Running a Management Command Inside a Container

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Development vs Production

| Aspect | Development (`docker-compose.yml`) | Production (`deployment/docker-compose.yml`) |
|---|---|---|
| Web server | Django `runserver` | Gunicorn behind Nginx |
| Static files | Served by Django | Pre-built and served by Nginx |
| Env file | `.env.dev` | `.env` |
| Hot reload | Yes (volume mount) | No |

## Environment Variables

Required variables are documented in `deployment/env.sample` and `deployment/env.dev.sample`. At minimum, set:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (or individual `POSTGRES_*` vars)
- `REDIS_URL`
- `SERVER_NAME` (production only)

See `DEPLOYMENT.md` for the full production setup walkthrough, including Nginx, SSL (certbot), and backup configuration.
