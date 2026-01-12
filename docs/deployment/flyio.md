# Deploying Eventyay to Fly.io

This guide outlines how to deploy Eventyay to [Fly.io](https://fly.io) using the provided `fly.toml` configuration.

## Prerequisites

- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed.
- A Fly.io account.

## Setup & Deployment

1.  **Login to Fly.io**:

    ```bash
    fly auth login
    ```

2.  **Initialize the App**:
    From the root of the repository, run:

    ```bash
    fly launch --no-deploy
    ```

    - Choose an app name (e.g., `eventyay-next`).
    - Select a region.
    - Select `N` for database (we'll set it up separately) or `Y` to provision a Development Postgres.
    - Select `N` for Redis (we'll set it up separately) or `Y` to provision Upstash Redis.

3.  **Database & Redis Setup**:

    - **Postgres**: Create a Fly Postgres cluster or use an external provider.
      ```bash
      fly postgres create
      fly postgres attach <postgres-app-name>
      ```
    - **Redis**: Create a Fly Redis (Upstash) or use an external provider.
      ```bash
      fly redis create
      ```
      Get the connection string and set it as secret:
      ```bash
      fly secrets set REDIS_URL=<redis-connection-string>
      ```

4.  **Configuration**:
    The `fly.toml` file defines three processes:

    - `web`: Django application
    - `worker`: Celery worker
    - `scheduler`: Celery Beat

    Ensure your secrets are set:

    ```bash
    fly secrets set EVY_SECRET_KEY='<random-secret>'
    fly secrets set EVY_ALLOWED_HOSTS='*'
    ```

5.  **Deploy**:
    ```bash
    fly deploy
    ```

## Multi-Process Architecture

Fly.io runs these processes as separate VMs (Firecrackers) within the same app context, scaling them independently.

- To scale the web process: `fly scale count web=2`
- To scale the worker: `fly scale count worker=1`

## Frontend Deployment

For the frontend, you can either:

1.  Serve it via Django (if configured with Whitenoise and collected static files).
2.  Deploy it as a separate Static site on Fly.io (requires a separate `fly.toml` in `app/eventyay/webapp`).

## Persistent Storage

If you need to store media files locally instead of S3, you must uncomment the `[[mounts]]` section in `fly.toml` and create a volume:

```bash
fly volumes create eventyay_data --region <your-region>
```

However, using S3-compatible storage is recommended for production.
