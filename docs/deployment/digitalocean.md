# Deploying Eventyay to DigitalOcean App Platform

This guide explains how to deploy Eventyay to [DigitalOcean App Platform](https://www.digitalocean.com/products/app-platform) using the provided `app.yaml` specification.

## Prerequisites

- A DigitalOcean account
- `doctl` CLI installed (optional but recommended)
- A fork of the [Eventyay repository](https://github.com/fossasia/eventyay)

## Deployment Options

### Option 1: Via Dashboard (Easiest)

1. Go to [Apps Dashboard](https://cloud.digitalocean.com/apps)
2. Click **Create App**
3. Choose **GitHub** as source
4. Select your repository and branch
5. On the Resources screen, click **Edit Spec**
6. Copy the content of `app.yaml` and paste it
7. Click **Save** then **Next**
8. Review and click **Create Resources**

### Option 2: Via CLI (Recommended)

#### 1. Install doctl

```bash
# macOS
brew install doctl

# Linux
snap install doctl

# Or download from https://github.com/digitalocean/doctl/releases
```

#### 2. Authenticate

```bash
doctl auth init
```

Follow the prompts to enter your API token.

#### 3. Create App

```bash
doctl apps create --spec app.yaml
```

This creates all services defined in the spec file.

## What Gets Deployed

### Services

- **eventyay-web**: Django application (public)
- **eventyay-worker**: Celery worker (internal)
- **eventyay-scheduler**: Celery Beat (internal)

### Databases

- **eventyay-db**: Managed PostgreSQL 15
- **eventyay-redis**: Managed Redis 7

## Environment Variables

DigitalOcean automatically configures:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `APP_DOMAIN`: Your app's domain
- `EVY_SECRET_KEY`: Set as SECRET type (add value in dashboard)

### Add Secret Key

After deployment:

1. Go to your app in the dashboard
2. Click **Settings** → **App-Level Environment Variables**
3. Find `EVY_SECRET_KEY`
4. Click **Edit** and add a secure random value

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## After Deployment

### Access Your Application

Your app will be available at:

```
https://<your-app-name>.ondigitalocean.app
```

### Check Deployment Status

```bash
# List apps
doctl apps list

# Get app details
doctl apps get <app-id>

# View logs
doctl apps logs <app-id> --type run
```

### Run Migrations

Migrations run automatically during deployment. To run manually:

1. Go to your app in the dashboard
2. Click on the **eventyay-web** component
3. Go to **Console** tab
4. Run:
   ```bash
   python manage.py migrate
   ```

## Scaling

### Via Dashboard

1. Go to your app
2. Click on a component (web, worker, or scheduler)
3. Click **Edit Plan**
4. Choose:
   - **Instance Size**: CPU and memory
   - **Instance Count**: Number of containers

### Via CLI

```bash
# Update app spec
doctl apps update <app-id> --spec app.yaml
```

Edit `app.yaml` to change:

- `instance_size_slug`: `basic-xxs`, `basic-xs`, `basic-s`, etc.
- `instance_count`: Number of instances

## Database Management

### Access Database

```bash
# Get connection details
doctl databases connection <database-id>

# Connect via psql
doctl databases connection <database-id> --format psql | psql
```

### Create Backup

DigitalOcean automatically backs up your database daily. To create manual backup:

1. Go to **Databases** in the dashboard
2. Select your database
3. Go to **Backups** tab
4. Click **Create Backup**

## Custom Domain

### Add Domain

1. Go to your app in the dashboard
2. Click **Settings** → **Domains**
3. Click **Add Domain**
4. Enter your domain name
5. Update DNS records as instructed

### Update Allowed Hosts

After adding a custom domain:

1. Go to **Settings** → **App-Level Environment Variables**
2. Update `EVY_ALLOWED_HOSTS` to include your domain:
   ```
   ["yourdomain.com", "www.yourdomain.com"]
   ```

## Monitoring

### View Metrics

1. Go to your app in the dashboard
2. Click **Insights** tab
3. View:
   - CPU usage
   - Memory usage
   - Request count
   - Response times

### Set Up Alerts

1. Go to **Monitoring** → **Alerts**
2. Create alerts for:
   - High CPU usage
   - High memory usage
   - Failed deployments

## Troubleshooting

### Build Failures

- Check build logs in the **Activity** tab
- Ensure Dockerfile is correct
- Verify all dependencies are available

### Database Connection Issues

- Ensure database is running
- Check `DATABASE_URL` is set correctly
- Verify network connectivity

### Worker Not Processing Tasks

- Check worker logs in the dashboard
- Ensure Redis is running
- Verify `REDIS_URL` is correct

## Cost Optimization

- Start with `basic-xxs` instances ($5/month each)
- Database starts at $15/month
- Redis starts at $15/month
- Scale up only when needed
- Use instance count for horizontal scaling

## Support

For DigitalOcean-specific issues:

- [App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [DigitalOcean Community](https://www.digitalocean.com/community)
- [Support Tickets](https://cloud.digitalocean.com/support/tickets)
