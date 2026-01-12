# Deploying Eventyay to Render

This guide outlines how to deploy the full Eventyay stack to [Render](https://render.com) using the provided `render.yaml` Blueprint.

## Prerequisites

- A [Render](https://render.com) account.
- A fork of the [Eventyay repository](https://github.com/fossasia/eventyay) connected to your Render account.

## One-Click Deployment

1.  Go to your Render Dashboard.
2.  Click **New +** and select **Blueprint**.
3.  Connect your repository.
4.  Render will automatically detect the `render.yaml` file.
5.  Review the services and resources to be created:
    - **Web Service**: The Django application.
    - **Worker Service**: Celery worker for background tasks.
    - **Scheduler Service**: Celery Beat for scheduled tasks.
    - **Frontend Service**: Static site for the Vue.js frontend.
    - **PostgreSQL**: Managed database.
    - **Redis**: Managed key-value store.
6.  Click **Apply Blueprint**.

## Service Details

### Web Service (Django)

- **Name**: `eventyay-next-web`
- **Environment**: Docker
- **Command**: `gunicorn eventyay.config.wsgi:application --bind 0.0.0.0:8000` (handled via Dockerfile entrypoint)

### Worker & Scheduler

- **Worker**: Runs simple Celery tasks.
- **Scheduler**: Runs periodic tasks using Celery Beat.

### Frontend

- **Name**: `eventyay-next-frontend`
- **Type**: Static Site
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`
- **Rewrite Rules**: All routes rewrite to `index.html` (SPA support).

## Environment Variables

The `render.yaml` blueprint automatically maps necessary environment variables between services, including:

- `DATABASE_URL` / `POSTGRES_HOST`, `POSTGRES_PORT`, etc.
- `REDIS_URL`

You can customize additional environment variables in the Render Dashboard under **Environment** for each service.

## Manual Configuration (Optional)

If you prefer determining services manually or need specific configurations (e.g., S3 storage, Email settings), you can add the following environment variables to your Web and Worker services:

- `EVY_EMAIL_HOST`
- `EVY_EMAIL_HOST_USER`
- `EVY_EMAIL_HOST_PASSWORD`
- `EVY_EMAIL_PORT`
- `EVY_EMAIL_USE_TLS`
- `AWS_ACCESS_KEY_ID` (if using S3)
- `AWS_SECRET_ACCESS_KEY` (if using S3)
- `AWS_STORAGE_BUCKET_NAME` (if using S3)

## Troubleshooting

- **Database Connections**: Ensure the `POSTGRES_HOST` allows connections from the internal network. Render Blueprints handle this automatically.
- **Static Assets**: If frontend assets are missing, check the Static Site build logs in Render.
