# Deploying Eventyay to DigitalOcean App Platform

This guide outlines how to deploy Eventyay to [DigitalOcean App Platform](https://www.digitalocean.com/products/app-platform) using the provided `app.yaml` specification.

## Prerequisites

- A DigitalOcean account.
- `doctl` CLI installed (optional, but recommended).

## Deployment Steps

### Option 1: Via Dashboard

1.  Go to the [Apps Dashboard](https://cloud.digitalocean.com/apps).
2.  Click **Create App**.
3.  Select **GitHub** as the source and choose your repository.
4.  DigitalOcean may try to auto-detect the configuration.
5.  Instead of default detection, look for an option to upload or use `app.yaml` from the repository (if available in the flow) or configure manually matching the structure.
6.  _Note_: The current `app.yaml` assumes the app is created from the spec.

### Option 2: Via CLI (Recommended)

1.  Authenticate:

    ```bash
    doctl auth init
    ```

2.  Create the App:

    ```bash
    doctl apps create --spec app.yaml
    ```

    This command will create:

    - **Web Service**: Django app.
    - **Worker**: Celery worker.
    - **Worker (Scheduler)**: Celery beat.
    - **Database**: Managed PostgreSQL.
    - **Redis**: Managed Redis.

3.  **Environment Variables**:
    The `app.yaml` defines keys like `EVY_SECRET_KEY` as type `SECRET`. You may need to update these values in the dashboard settings after creation if they are empty or set them during creation.

## Managed Services

DigitalOcean App Platform handles the provisioning of the Database and Redis. The connection strings (`DATABASE_URL`, `REDIS_URL`) are automatically injected into the application environment.

## Scaling

You can scale the services (Web, Worker) vertically (size) or horizontally (count) via the Dashboard or by updating `app.yaml` and applying the update:

```bash
doctl apps update <app-id> --spec app.yaml
```
