# Docker Deploy Checklist

## Compose Inputs

- `docker-compose.yml` exists for development.
- `deployment/docker-compose.yml` exists for production.
- Required env files are present and updated.

## Runtime Behavior

- Development stack uses Django runserver.
- Production stack uses pre-built image and Gunicorn.
- Host-level Nginx reverse proxies to the app in production.

## Operational Checks

- Database migrations are applied.
- Worker and web logs show healthy startup.
- Rollback path is documented before risky deployments.
