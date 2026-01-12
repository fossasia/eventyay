# Deploying Eventyay to Zeabur

This guide outlines how to deploy Eventyay to [Zeabur](https://zeabur.com) using the provided `zeabur.yaml` configuration.

## Deployment Steps

1.  **Fork the Repository**: Ensure you have a fork of Eventyay in your GitHub account.
2.  **Go to Zeabur Dashboard**: Log in to [Zeabur](https://zeabur.com).
3.  **Create New Project**:
    - Select your region.
    - Click **Deploy New Service**.
    - Select **GitHub**.
    - Choose your Eventyay fork.
4.  **Configuration**:
    - Zeabur should detect the `zeabur.yaml` configuration and prompt to create the defined services:
      - **eventyay-web**
      - **eventyay-worker**
      - **eventyay-scheduler**
      - **eventyay-frontend**
      - **PostgreSQL**
      - **Redis**
5.  **Environment Variables**:
    - Zeabur automatically links the Database and Redis services and injects `DATABASE_URL` and `REDIS_URL`.
    - Verify that `EVY_SECRET_KEY` is generated or add it manually in the Variables tab if missing.

## Service Details

- **Web**: Runs the Django application.
- **Worker/Scheduler**: Runs Celery processes.
- **Frontend**: Deploys as a static site.
