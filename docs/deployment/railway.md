# Deploying Eventyay to Railway

This guide explains how to deploy Eventyay to [Railway](https://railway.app) using the provided `railway.json` template.

## Prerequisites

- A [Railway](https://railway.app) account
- A fork of the [Eventyay repository](https://github.com/fossasia/eventyay)

## Deployment Steps

### 1. Create New Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Choose your forked repository
5. Railway will detect `railway.json` automatically

### 2. Review Services

Railway will create:

- **Web**: Django application server
- **Worker**: Celery background worker
- **Scheduler**: Celery Beat for periodic tasks
- **Frontend**: Vue.js static site
- **Postgres**: Managed PostgreSQL database
- **Redis**: Managed Redis instance

### 3. Deploy

Click **Deploy** and Railway will:

1. Build the Docker image
2. Create database and Redis instances
3. Link services together
4. Start all services

## Environment Variables

Railway automatically configures:

- `EVY_SECRET_KEY`: Auto-generated
- `DATABASE_URL`: Linked from Postgres service
- `REDIS_URL`: Linked from Redis service
- `PORT`: Assigned by Railway

All services share the same environment variables.

## After Deployment

### Access Your Application

1. Go to the Web service
2. Click **Settings** → **Networking**
3. Click **Generate Domain**
4. Your app will be available at the generated URL

### Check Logs

1. Click on any service
2. View real-time logs in the **Deployments** tab
3. Check for any errors or warnings

### Run Migrations

Migrations run automatically. To run manually:

1. Go to Web service
2. Click on the latest deployment
3. Open **Shell** and run:
   ```bash
   python manage.py migrate
   ```

## Service Configuration

### Web Service

- **Build**: Uses `app/Dockerfile`
- **Start Command**: `gunicorn eventyay.config.wsgi:application --bind 0.0.0.0:$PORT`
- **Port**: Automatically assigned by Railway

### Worker Service

- **Build**: Same Dockerfile as Web
- **Start Command**: `celery -A eventyay worker -l info`
- **Environment**: Shares Web service variables

### Scheduler Service

- **Build**: Same Dockerfile as Web
- **Start Command**: `celery -A eventyay beat -l info`
- **Environment**: Shares Web service variables

### Frontend Service

- **Root**: `app/eventyay/webapp`
- **Build**: `npm install && npm run build`
- **Start**: `npm run preview -- --port $PORT --host 0.0.0.0`

## Custom Configuration

### Add Environment Variables

1. Go to your service
2. Click **Variables**
3. Add new variables:
   - Email settings (`EVY_EMAIL_*`)
   - S3 storage (`AWS_*`)
   - Custom domain (`EVY_ALLOWED_HOSTS`)

### Scale Services

1. Go to service **Settings**
2. Adjust **Resources**:
   - CPU
   - Memory
   - Replicas (for horizontal scaling)

## Database Management

### Access Database

1. Go to Postgres service
2. Click **Data** tab to browse tables
3. Or use **Connect** to get connection details

### Backup Database

Railway automatically backs up your database. To create manual backup:

1. Go to Postgres service
2. Click **Backups**
3. Click **Create Backup**

## Troubleshooting

### Build Failures

- Check build logs in the deployment
- Ensure Dockerfile is correct
- Verify all dependencies are listed

### Database Connection Issues

- Ensure Postgres service is running
- Check that `DATABASE_URL` is set
- Verify network connectivity between services

### Worker Not Processing Tasks

- Check Worker logs for errors
- Ensure Redis service is running
- Verify `REDIS_URL` is correct

## Cost Management

- Railway offers $5 free credit monthly
- Pay only for what you use
- Monitor usage in **Usage** tab
- Set spending limits in **Settings**

## Support

For Railway-specific issues:

- [Railway Documentation](https://docs.railway.app)
- [Railway Discord](https://discord.gg/railway)
