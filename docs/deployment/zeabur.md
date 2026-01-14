# Deploying Eventyay to Zeabur

This guide explains how to deploy Eventyay to [Zeabur](https://zeabur.com) using the provided `zeabur.yaml` configuration.

## Prerequisites

- A Zeabur account
- A fork of the [Eventyay repository](https://github.com/fossasia/eventyay)

## Deployment Steps

### 1. Create New Project

1. Go to [Zeabur Dashboard](https://zeabur.com/dashboard)
2. Click **Create Project**
3. Choose your preferred region
4. Give your project a name

### 2. Deploy from GitHub

1. Click **Deploy New Service**
2. Select **GitHub**
3. Choose your Eventyay fork
4. Select the branch to deploy

### 3. Auto-Detection

Zeabur will automatically:

- Detect the `zeabur.yaml` configuration
- Create all defined services
- Set up databases
- Link services together

### 4. Review Services

Zeabur creates:

- **eventyay-web**: Django application
- **eventyay-worker**: Celery worker
- **eventyay-scheduler**: Celery Beat
- **eventyay-frontend**: Vue.js static site
- **eventyay-db**: PostgreSQL database
- **eventyay-redis**: Redis instance

## Environment Variables

Zeabur automatically configures:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `EVY_RUNNING_ENVIRONMENT`: Set to `production`
- `EVY_ALLOWED_HOSTS`: Set to `["*"]`

### Add Secret Key

1. Go to your project
2. Click on **eventyay-web** service
3. Go to **Variables** tab
4. Add `EVY_SECRET_KEY`:
   ```bash
   # Generate a secret key
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
5. Paste the generated key

## After Deployment

### Access Your Application

1. Go to your **eventyay-web** service
2. Click on the **Domains** tab
3. Zeabur provides a default domain:
   ```
   https://<service-name>-<random-id>.zeabur.app
   ```

### Check Deployment Status

1. Click on any service
2. View **Logs** tab for real-time logs
3. Check **Metrics** for performance data

### Run Migrations

Migrations run automatically. To run manually:

1. Go to **eventyay-web** service
2. Click **Console** tab
3. Run:
   ```bash
   python manage.py migrate
   ```

## Service Configuration

### Web Service

- **Build**: Uses `app/Dockerfile`
- **Port**: 8000 (HTTP)
- **Public**: Yes (accessible via domain)

### Worker Service

- **Build**: Same Dockerfile
- **Command**: `celery -A eventyay worker -l info`
- **Public**: No (internal only)

### Scheduler Service

- **Build**: Same Dockerfile
- **Command**: `celery -A eventyay beat -l info`
- **Public**: No (internal only)

### Frontend Service

- **Build**: `npm install && npm run build`
- **Output**: `dist` directory
- **Port**: 8080 (HTTP)
- **Public**: Yes

## Custom Configuration

### Add Environment Variables

1. Go to your service
2. Click **Variables** tab
3. Add variables:
   - Email settings (`EVY_EMAIL_*`)
   - S3 storage (`AWS_*`)
   - Custom settings

### Custom Domain

1. Go to **eventyay-web** service
2. Click **Domains** tab
3. Click **Add Domain**
4. Enter your domain
5. Update DNS records as instructed:
   ```
   CNAME  @  <your-service>.zeabur.app
   ```

## Scaling

### Vertical Scaling

1. Go to your service
2. Click **Settings**
3. Adjust resources:
   - CPU
   - Memory
   - Disk space

### Horizontal Scaling

Zeabur automatically scales based on traffic. To configure:

1. Go to service **Settings**
2. Set **Auto Scaling** parameters:
   - Minimum instances
   - Maximum instances
   - Target CPU usage

## Database Management

### Access Database

1. Go to **eventyay-db** service
2. Click **Connect** to get connection details
3. Use any PostgreSQL client to connect

### Backup Database

Zeabur automatically backs up your database. To create manual backup:

1. Go to **eventyay-db** service
2. Click **Backups** tab
3. Click **Create Backup**

## Monitoring

### View Logs

1. Go to any service
2. Click **Logs** tab
3. View real-time logs
4. Filter by log level or search

### View Metrics

1. Go to any service
2. Click **Metrics** tab
3. View:
   - CPU usage
   - Memory usage
   - Network traffic
   - Request count

## Troubleshooting

### Build Failures

- Check build logs in the service
- Ensure Dockerfile is correct
- Verify dependencies are available

### Database Connection Issues

- Ensure database service is running
- Check `DATABASE_URL` is set
- Verify network connectivity

### Worker Not Processing Tasks

- Check worker logs
- Ensure Redis is running
- Verify `REDIS_URL` is correct

### Static Files Not Loading

- Check frontend build logs
- Ensure `npm run build` succeeded
- Verify `dist` directory exists

## Cost Management

- Free tier available for testing
- Pay-as-you-go pricing
- Monitor usage in **Billing** tab
- Set spending limits to avoid surprises

## Support

For Zeabur-specific issues:

- [Zeabur Documentation](https://zeabur.com/docs)
- [Zeabur Discord](https://discord.gg/zeabur)
- [GitHub Issues](https://github.com/zeabur/zeabur/issues)
