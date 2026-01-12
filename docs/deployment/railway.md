# Deploying Eventyay to Railway

This guide outlines how to deploy Eventyay to [Railway](https://railway.app) using the provided `railway.json` template configuration.

## One-Click Deployment

The easiest way to deploy is to use the Railway Template feature (if this repo is published as a template) or by manually creating a new project from your fork.

1.  **Fork the Repository**: Ensure you have a fork of [Eventyay](https://github.com/fossasia/eventyay) in your GitHub account.
2.  **New Project on Railway**:
    - Go to [Railway Dashboard](https://railway.app/dashboard).
    - Click **New Project** > **Deploy from GitHub repo**.
    - Select your forked repository.
    - Railway should verify the `railway.json` and suggest the services defined there.

## Service Configuration

The `railway.json` defines the following services:

### 1. Web Service

- **Description**: The main Django application server.
- **Build**: Dockerfile in `app/Dockerfile`.
- **Start Command**: `gunicorn eventyay.config.wsgi:application --bind 0.0.0.0:$PORT`
- **Environment Variables**:
  - `EVY_SECRET_KEY`: Auto-generated.
  - `DATABASE_URL`: Linked from Postgres service.
  - `REDIS_URL`: Linked from Redis service.

### 2. Worker Service

- **Description**: Background task worker (Celery).
- **Build**: Same Dockerfile.
- **Start Command**: `celery -A eventyay worker -l info`

### 3. Scheduler Service

- **Description**: Periodic task scheduler (Celery Beat).
- **Build**: Same Dockerfile.
- **Start Command**: `celery -A eventyay beat -l info`

### 4. Frontend Service

- **Description**: Vue.js Frontend.
- **Root**: `app/eventyay/webapp`
- **Build Command**: `npm install && npm run build`
- **Start Command**: `npm run preview -- --port $PORT --host 0.0.0.0` (or serves static files via extensive setup).

_Note: For production, you may want to serve the frontend via the Web service (Django) or use a specialized Static Site Hosting._

### Databases

- **Postgres**: Managed PostgreSQL instance.
- **Redis**: Managed Redis instance.

## Post-Deployment

- Ensure that the `Web` service is public and accessible.
- Check logs for any migration or startup issues.
