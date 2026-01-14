# Deploying Eventyay to Google Cloud Platform

This guide explains how to deploy Eventyay to Google Cloud Platform using Cloud Run, Cloud SQL, and Memorystore.

## Prerequisites

- A [Google Cloud Platform](https://cloud.google.com) account
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and configured
- A fork of the [Eventyay repository](https://github.com/fossasia/eventyay)

## Quick Start

The deployment is automated using a single script:

```bash
./scripts/finish_prod_setup.sh
```

This script will:

1. Build the Docker image
2. Run database migrations
3. Deploy web and worker services
4. Configure networking and access

## Initial Setup

Before running the deployment script, you need to set up the required GCP resources.

### 1. Create a GCP Project

```bash
gcloud projects create YOUR-PROJECT-ID
gcloud config set project YOUR-PROJECT-ID
```

### 2. Enable Required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 3. Create Cloud SQL Database

```bash
# Create PostgreSQL instance
gcloud sql instances create eventyay-db-prod \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database user
gcloud sql users create eventyay_user \
    --instance=eventyay-db-prod \
    --password=YOUR_SECURE_PASSWORD

# Create database
gcloud sql databases create eventyay_db \
    --instance=eventyay-db-prod
```

### 4. Create Redis Instance

```bash
gcloud redis instances create eventyay-redis-prod \
    --size=1 \
    --region=us-central1 \
    --redis-version=redis_7_0
```

### 5. Store Secrets

```bash
# Database password
echo -n "YOUR_SECURE_PASSWORD" | \
    gcloud secrets create eventyay-db-password --data-file=-

# Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" | \
    gcloud secrets create eventyay-secret-key --data-file=-

# Redis URL (get IP from previous step)
REDIS_IP=$(gcloud redis instances describe eventyay-redis-prod --region=us-central1 --format="value(host)")
echo -n "redis://${REDIS_IP}:6379" | \
    gcloud secrets create eventyay-redis-url --data-file=-
```

## Configuration Files

The deployment uses three YAML configuration files:

- `cloudrun-web.yaml` - Web service configuration
- `cloudrun-worker.yaml` - Background worker configuration
- `cloudrun-migration.yaml` - Database migration job

Update the `EVY_SITE_URL` in `cloudrun-web.yaml` to match your Cloud Run service URL.

## Architecture

### Services

- **Web Service**: Django application serving HTTP requests
- **Worker Service**: Celery worker for background tasks
- **Migration Job**: One-time job for database migrations

### Databases

- **Cloud SQL (PostgreSQL)**: Main application database
- **Memorystore (Redis)**: Caching and task queue

### Networking

- **VPC Egress**: `private-ranges-only` mode
  - Redis traffic goes through VPC
  - Cloud SQL Proxy uses public internet

## Environment Variables

The following environment variables are configured automatically:

- `EVY_RUNNING_ENVIRONMENT`: Set to `production`
- `EVY_SITE_URL`: Your Cloud Run service URL
- `EVY_POSTGRES_*`: Database connection details
- `EVY_REDIS_URL`: Redis connection string
- `EVY_SECRET_KEY`: Django secret key

All sensitive values are stored in Google Secret Manager.

## Deployment Process

### First Deployment

1. Clone your fork:

   ```bash
   git clone https://github.com/YOUR-USERNAME/eventyay.git
   cd eventyay
   ```

2. Update configuration files with your project details

3. Run the deployment script:

   ```bash
   ./scripts/finish_prod_setup.sh
   ```

4. Access your application at the provided Cloud Run URL

### Subsequent Deployments

Simply run the deployment script again:

```bash
./scripts/finish_prod_setup.sh
```

The script handles:

- Rebuilding the Docker image
- Running new migrations
- Deploying updated services

## Monitoring

View logs in the Google Cloud Console:

```bash
# Web service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=eventyay-next-web" --limit=50

# Worker service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=eventyay-next-worker" --limit=50
```

## Scaling

Cloud Run automatically scales based on traffic. To configure scaling:

```bash
# Set minimum instances (to avoid cold starts)
gcloud run services update eventyay-next-web \
    --min-instances=1 \
    --region=us-central1

# Set maximum instances
gcloud run services update eventyay-next-web \
    --max-instances=10 \
    --region=us-central1
```

## Custom Domain

To use a custom domain:

1. Verify domain ownership in Google Cloud Console
2. Map your domain to the Cloud Run service:
   ```bash
   gcloud run domain-mappings create \
       --service=eventyay-next-web \
       --domain=yourdomain.com \
       --region=us-central1
   ```
3. Update DNS records as instructed

## Troubleshooting

### Database Connection Issues

- Verify Cloud SQL instance is running
- Check that the database `eventyay_db` exists
- Ensure secrets are correctly set in Secret Manager

### Static Files Not Loading

- Verify `collectstatic` ran during build
- Check that `COMPRESS_OFFLINE=True` in settings
- Ensure static files are in the Docker image

### Redis Connection Errors

- Verify Memorystore instance is running
- Check VPC networking configuration
- Ensure `eventyay-redis-url` secret has correct IP

## Cost Optimization

- Use `db-f1-micro` tier for development
- Set `--min-instances=0` to avoid idle costs
- Use Cloud Scheduler to warm up instances before peak hours

## Security

- All secrets stored in Secret Manager
- Database accessible only via Unix socket
- Redis accessible only via private VPC
- HTTPS enforced by default on Cloud Run

## Support

For issues specific to GCP deployment, check:

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Memorystore Documentation](https://cloud.google.com/memorystore/docs)
