# Deploying Eventyay to Google Cloud Run

This guide outlines how to deploy Eventyay to [Google Cloud Run](https://cloud.google.com/run) using the provided `cloudrun.yaml` configuration (split into `cloudrun-web.yaml` and `cloudrun-worker.yaml`).

## Prerequisites

- Google Cloud Platform (GCP) Project.
- `gcloud` CLI installed and authenticated.
- Cloud SQL (PostgreSQL) instance created.
- Cloud Memorystore (Redis) instance created.

## Deployment Steps

1.  **Build and Push Container Image**:
    You need to build the Docker image and push it to Google Container Registry (GCR) or Artifact Registry.

    ```bash
    export PROJECT_ID=$(gcloud config get-value project)
    gcloud builds submit --tag gcr.io/$PROJECT_ID/eventyay-next app/
    ```

2.  **Create Secrets**:
    Store sensitive configuration in Secret Manager.

    ```bash
    echo -n "postgres://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE" | gcloud secrets create eventyay-database-url --data-file=-
    echo -n "redis://HOST:PORT" | gcloud secrets create eventyay-redis-url --data-file=-
    # ... Create other secrets and map them in cloudrun.yaml
    ```

3.  **Update `cloudrun.yaml`**:

    - Replace `PROJECT_ID` with your actual project ID.
    - Replace `PROJECT_ID:REGION:INSTANCE_NAME` with your Cloud SQL connection name.
    - Ensure secret names match what you created.

4.  **Deploy Services**:

    ```bash
    gcloud run services replace cloudrun-web.yaml
    gcloud run services replace cloudrun-worker.yaml
    ```

    This will deploy both the `eventyay-next-web` and `eventyay-next-worker` services.

    By default, Cloud Run services are private. To allow public access to the website:

    ```bash
    gcloud run services add-iam-policy-binding eventyay-next-web \
      --member="allUsers" \
      --role="roles/run.invoker"
    ```

    _Note_: The Worker service is configured with `minScale: 1` and CPU throttling disabled to ensure it runs continuously for background tasks.

## Static Assets

For Cloud Run, it's recommended to serve static assets via Google Cloud Storage (GCS) and a CDN (Cloud IaaS), or use Whitenoise within the application. Using Whitenoise is simpler for initial setup:

- Ensure `whitenoise` middleware is enabled in Django settings (it is by default in Eventyay).

## Domain Mapping

You can map a custom domain to your Cloud Run service via the **Manage Custom Domains** page in the Console or using `gcloud beta run domain-mappings create`.
