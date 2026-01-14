# Deploying Eventyay to Fly.io

This guide explains how to deploy Eventyay to [Fly.io](https://fly.io) using the provided `fly.toml` configuration.

## Prerequisites

- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed
- A Fly.io account

## Initial Setup

### 1. Install flyctl

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### 2. Login to Fly.io

```bash
fly auth login
```

### 3. Create App

From the repository root:

```bash
fly launch --no-deploy
```

When prompted:

- Choose an app name (e.g., `eventyay-next`)
- Select a region close to your users
- Say **No** to Postgres (we'll set it up separately)
- Say **No** to Redis (we'll set it up separately)

## Database Setup

### Create PostgreSQL Database

```bash
# Create Postgres cluster
fly postgres create

# Attach to your app
fly postgres attach <postgres-app-name>
```

This automatically sets the `DATABASE_URL` environment variable.

### Create Redis Instance

```bash
# Create Redis (Upstash)
fly redis create

# Get connection string
fly redis status <redis-name>

# Set as secret
fly secrets set REDIS_URL=<redis-connection-string>
```

## Configuration

### Set Required Secrets

```bash
# Django secret key
fly secrets set EVY_SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

# Allowed hosts
fly secrets set EVY_ALLOWED_HOSTS='["*.fly.dev"]'
```

### Review fly.toml

The `fly.toml` file defines three processes:

- **web**: Django application (public)
- **worker**: Celery worker (internal)
- **scheduler**: Celery Beat (internal)

## Deploy

```bash
fly deploy
```

This will:

1. Build the Docker image
2. Push to Fly.io registry
3. Deploy all three processes
4. Run health checks

## After Deployment

### Access Your Application

Your app will be available at:

```
https://<your-app-name>.fly.dev
```

### Check Status

```bash
# View app status
fly status

# View logs
fly logs

# SSH into app
fly ssh console
```

### Run Migrations

```bash
# Run migrations
fly ssh console -C "python manage.py migrate"

# Create superuser
fly ssh console -C "python manage.py createsuperuser"
```

## Scaling

### Horizontal Scaling

```bash
# Scale web process
fly scale count web=2

# Scale worker process
fly scale count worker=3
```

### Vertical Scaling

```bash
# Change machine size
fly scale vm shared-cpu-1x --memory 512
```

### Auto-scaling

```bash
# Set auto-scaling limits
fly autoscale set min=1 max=10
```

## Multi-Process Architecture

Fly.io runs each process as a separate VM:

- **web**: Handles HTTP requests (public)
- **worker**: Processes background tasks (internal)
- **scheduler**: Runs periodic tasks (internal)

All processes share the same environment variables and secrets.

## Persistent Storage

### For Media Files

If you need local file storage:

```bash
# Create volume
fly volumes create eventyay_data --region <your-region> --size 10

# Uncomment [[mounts]] section in fly.toml
```

**Note**: Using S3-compatible storage is recommended for production.

## Custom Domain

### Add Domain

```bash
# Add domain
fly certs add yourdomain.com

# Add www subdomain
fly certs add www.yourdomain.com
```

### Update DNS

Add these records to your DNS:

```
A     @     <fly-ip-address>
AAAA  @     <fly-ipv6-address>
CNAME www   <your-app-name>.fly.dev
```

Get IP addresses with:

```bash
fly ips list
```

## Monitoring

### View Metrics

```bash
# View metrics
fly dashboard metrics

# View logs
fly logs --app <your-app-name>
```

### Set Up Alerts

1. Go to [Fly.io Dashboard](https://fly.io/dashboard)
2. Select your app
3. Go to **Monitoring**
4. Configure alerts for:
   - High CPU usage
   - Memory limits
   - Failed health checks

## Troubleshooting

### Build Failures

```bash
# View build logs
fly logs --app <your-app-name>

# Try local build
fly deploy --local-only
```

### Database Connection Issues

```bash
# Check Postgres status
fly postgres db list --app <postgres-app-name>

# View connection string
fly postgres connect --app <postgres-app-name>
```

### Health Check Failures

```bash
# Check health endpoint
curl https://<your-app-name>.fly.dev/

# View detailed logs
fly logs --app <your-app-name>
```

## Cost Optimization

- Free tier includes 3 shared-cpu-1x VMs
- Postgres and Redis have separate free tiers
- Stop unused apps: `fly apps destroy <app-name>`
- Use `fly scale count web=0` to pause without destroying

## Support

For Fly.io-specific issues:

- [Fly.io Documentation](https://fly.io/docs)
- [Fly.io Community](https://community.fly.io)
