# Deploying Eventyay to Render

This guide explains how to deploy Eventyay to [Render](https://render.com) using the provided `render.yaml` blueprint.

## Prerequisites

- A [Render](https://render.com) account
- A fork of the [Eventyay repository](https://github.com/fossasia/eventyay)

## One-Click Deployment

1. Go to your [Render Dashboard](https://dashboard.render.com)
2. Click **New +** and select **Blueprint**
3. Connect your GitHub repository
4. Render will detect the `render.yaml` file automatically
5. Review the services to be created
6. Click **Apply Blueprint**

## What Gets Deployed

### Services

- **Web Service**: Django application (accessible via HTTPS)
- **Worker Service**: Celery worker for background tasks
- **Scheduler Service**: Celery Beat for periodic tasks
- **Frontend Service**: Vue.js static site

### Databases

- **PostgreSQL**: Managed database (free tier available)
- **Redis**: Managed key-value store (free tier available)

## Environment Variables

Render automatically configures these variables:

- `EVY_SECRET_KEY`: Auto-generated Django secret
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `POSTGRES_*`: Individual database connection parameters

All services share the same secret key and database connections.

## After Deployment

### Access Your Application

Your web service will be available at:

```
https://eventyay-next-web.onrender.com
```

### Check Service Status

1. Go to your Render Dashboard
2. Click on each service to view logs
3. Ensure all services show "Live" status

### Run Database Migrations

Migrations run automatically during the first deployment. To run them manually:

1. Go to the Web service in your dashboard
2. Click **Shell**
3. Run:
   ```bash
   python manage.py migrate
   ```

## Custom Configuration

### Email Settings

Add these environment variables to the Web service:

- `EVY_EMAIL_HOST`
- `EVY_EMAIL_HOST_USER`
- `EVY_EMAIL_HOST_PASSWORD`
- `EVY_EMAIL_PORT`
- `EVY_EMAIL_USE_TLS`

### File Storage (S3)

Add these environment variables for S3 storage:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`

## Scaling

### Upgrade Service Plan

1. Go to your service in the dashboard
2. Click **Settings**
3. Select a different instance type under **Instance Type**

### Scale Workers

To run multiple worker instances:

1. Go to the Worker service
2. Click **Settings**
3. Increase **Number of Instances**

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL service is running
- Check that `DATABASE_URL` is set correctly
- Verify the database was created successfully

### Static Files Not Loading

- Check the Frontend service build logs
- Ensure `npm run build` completed successfully
- Verify the `dist` directory was created

### Worker Not Processing Tasks

- Check Worker service logs for errors
- Ensure `REDIS_URL` is set correctly
- Verify Celery is connecting to Redis

## Cost Optimization

- Free tier includes 750 hours/month per service
- Database and Redis have separate free tiers
- Upgrade only the services that need more resources

## Support

For Render-specific issues:

- [Render Documentation](https://render.com/docs)
- [Render Community](https://community.render.com)
