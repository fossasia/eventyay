````md
# Eventyay Production Deployment Guide

This guide describes a production/self-hosted deployment of Eventyay using Docker Compose, PostgreSQL, Redis, nginx, certbot, and the deployment files in `deployment/`.

For local development, use the Docker quick start in `README.rst`. This file is intended for production or production-like server deployments.

## Contents

- [Scope](#scope)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Variables](#variables)
- [Server preparation](#server-preparation)
- [Install Docker](#install-docker)
- [Create deployment user](#create-deployment-user)
- [Create deployment directory](#create-deployment-directory)
- [Create data directories](#create-data-directories)
- [Configure environment](#configure-environment)
- [Install nginx and certbot](#install-nginx-and-certbot)
- [Configure nginx](#configure-nginx)
- [Configure SSL](#configure-ssl)
- [Start Eventyay](#start-eventyay)
- [Initial verification](#initial-verification)
- [Backups](#backups)
- [Updating Eventyay](#updating-eventyay)
- [Database and media migration](#database-and-media-migration)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)

## Scope

This guide assumes a single-server Docker Compose deployment.

The deployment uses:

- Docker Compose for application services
- PostgreSQL for database storage
- Redis for cache, broker, and background task support
- Gunicorn for the Django web application
- Daphne for ASGI/websocket traffic
- Celery worker and Celery beat for background tasks
- nginx as reverse proxy
- certbot for TLS certificates
- rclone for optional remote backups

This guide does not cover high-availability deployments, managed Kubernetes deployments, managed PostgreSQL services, or multi-node scaling.

## Architecture

The production Docker Compose setup starts the following services:

- `web`: Django application served by Gunicorn on port `8000`
- `websocket`: ASGI/Daphne service on port `8001`
- `worker`: Celery worker
- `beat`: Celery beat scheduler
- `db`: PostgreSQL 15
- `redis`: Redis
- `watchtower`: optional container updater

nginx should terminate HTTPS and proxy application traffic to the Docker services.

Typical request flow:

```text
Browser
  |
  | HTTPS
  v
nginx
  |
  | HTTP proxy
  +--> web:8000       Django / Gunicorn
  |
  +--> websocket:8001 ASGI / Daphne
````

Persistent data is stored below `DATA_DIR`.

Typical data layout:

```text
DATA_DIR/
├── data/       Uploaded files and application data
├── postgres/   PostgreSQL data directory
└── static/     Collected static files
```

## Requirements

Minimum starting point:

* Ubuntu server
* root or sudo access
* DNS record pointing to the server
* ports `80` and `443` open
* Docker and Docker Compose plugin
* nginx
* certbot
* 4 GB RAM minimum
* 80 GB disk minimum

Sizing depends on traffic, number of events, uploaded files, badge/PDF generation, logs, backups, and PostgreSQL growth.

Before deployment, prepare:

* public domain name, for example `eventyay.example.org`
* operational email address for certbot and server notifications
* SMTP credentials for outgoing email
* backup location, if remote backups are required
* strong production passwords and secrets

## Variables

The setup uses both temporary shell variables and persistent `.env` values.

Shell variables are used while executing setup commands. The `.env` file is used by Docker Compose, Eventyay containers, and backup scripts.

| Variable                      | Where used                | Purpose                                         |
| ----------------------------- | ------------------------- | ----------------------------------------------- |
| `USER`                        | shell/server              | Linux user running the deployment               |
| `DEPLOYMENT_NAME`             | shell and `.env`          | Deployment directory and backup namespace       |
| `SERVER_NAME`                 | shell, `.env`, nginx      | Public domain name                              |
| `DATA_DIR`                    | `.env` and Docker Compose | Persistent data path                            |
| `FULL_DATA_DIR`               | shell                     | Absolute resolved path to `DATA_DIR`            |
| `MANAGEMENT_EMAIL`            | `.env` and certbot        | Certbot and operational email                   |
| `TAG`                         | `.env`                    | Docker image tag, usually `main` for production |
| `EVY_SECRET_KEY`              | `.env`                    | Django secret key                               |
| `EVY_ALLOWED_HOSTS`           | `.env`                    | Allowed Django hosts                            |
| `WATCHTOWER_NOTIFICATION_URL` | `.env`                    | Optional Watchtower update notifications        |

Example shell variables:

```bash
export USER=eventyay
export DEPLOYMENT_NAME=eventyay-production
export SERVER_NAME=eventyay.example.org
export DATA_DIR=./data
export MANAGEMENT_EMAIL=admin@example.org
```

Use values that match your server and domain.

## Server preparation

Log into the server as root or a sudo-capable user.

Update packages:

```bash
apt update
apt upgrade
```

Install basic tools:

```bash
apt install ca-certificates curl git rsync
```

Reboot after major system upgrades if required:

```bash
systemctl reboot
```

Reconnect to the server after reboot.

## Install Docker

Remove older Docker-related packages if present:

```bash
apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)
```

Install Docker repository dependencies:

```bash
apt update
apt install ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
```

Add Docker's official apt repository:

```bash
tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Install Docker and the Compose plugin:

```bash
apt update
apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Check Docker:

```bash
docker --version
docker compose version
```

## Create deployment user

Create the Linux user that will run the deployment:

```bash
adduser $USER
adduser $USER docker
```

Allow nginx to read files below the deployment user's home directory:

```bash
chmod 0755 /home/$USER
```

Log out and log back in, or restart the session, so Docker group membership takes effect for the deployment user.

## Create deployment directory

Create the deployment directory:

```bash
mkdir -p /home/$USER/$DEPLOYMENT_NAME
chown -R $USER:$USER /home/$USER/$DEPLOYMENT_NAME
```

Switch to the deployment user:

```bash
su - $USER
```

Clone the repository:

```bash
cd /home/$USER/$DEPLOYMENT_NAME
git clone https://github.com/fossasia/eventyay.git
cd eventyay
git checkout main
cd ..
```

Link the production Docker Compose file into the deployment directory:

```bash
ln -s eventyay/deployment/docker-compose.yml docker-compose.yml
```

Create the production `.env` file from the sample:

```bash
if [ ! -r .env ]; then
  cp eventyay/deployment/env.sample .env
fi
```

## Create data directories

Resolve the full data directory path.

If `DATA_DIR` is absolute, use it directly. If it is relative, it is interpreted relative to `/home/$USER/$DEPLOYMENT_NAME`.

Run as root or with sudo:

```bash
if [[ $DATA_DIR == /* ]]; then
  FULL_DATA_DIR=$DATA_DIR
else
  FULL_DATA_DIR=/home/$USER/$DEPLOYMENT_NAME/$DATA_DIR
fi

mkdir -p "$FULL_DATA_DIR"
mkdir -p "$FULL_DATA_DIR/data"
mkdir -p "$FULL_DATA_DIR/postgres"
mkdir -p "$FULL_DATA_DIR/static"

chown -R $USER:$USER "$FULL_DATA_DIR"
chown -R $USER:$USER /home/$USER/$DEPLOYMENT_NAME
```

Set permissions required by the current container image:

```bash
chown 100:101 "$FULL_DATA_DIR/data"
chmod ugo+rwx "$FULL_DATA_DIR/static"
```

These ownership values must match the user/group expected by the container image. Review them when the image user changes.

The broad static file permission is currently used to ensure the container and nginx can write/read static files. If the deployment is hardened later, replace this with more specific group ownership and permissions.

## Configure environment

Edit the deployment `.env` file:

```bash
cd /home/$USER/$DEPLOYMENT_NAME
nano .env
```

Review at least the following values before starting production:

```text
TAG=main
DATA_DIR=./data
DEPLOYMENT_NAME=CHANGEME
MANAGEMENT_EMAIL=some@foo.com

EVY_DEBUG=0
EVY_RUNNING_ENVIRONMENT=production
EVY_SITE_URL=https://<SERVER_NAME>
EVY_TALK_HOSTNAME=https://<SERVER_NAME>
EVY_SECRET_KEY=CHANGEME
EVY_ALLOWED_HOSTS='[ "<SERVER_NAME>" ]'

EVY_POSTGRES_DB=CHANGEME_db
EVY_POSTGRES_USER=CHANGEME_user
EVY_POSTGRES_PASSWORD=CHANGEME_pass
EVY_POSTGRES_HOST=eventyay-next-db
EVY_POSTGRES_PORT=5432

POSTGRES_DB=CHANGEME_db
POSTGRES_USER=CHANGEME_user
POSTGRES_PASSWORD=CHANGEME_pass

EVY_EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EVY_EMAIL_HOST='CHANGE.ME.SERVER'
EVY_DEFAULT_FROM_EMAIL='CHANGE@ME.COM'
EVY_EMAIL_HOST_USER='CHANGE@ME.COM'
EVY_EMAIL_HOST_PASSWORD='CHANGEME_email_pass'
EVY_EMAIL_USE_TLS=1

BACKUP_LOCAL_LOCATION=$HOME/backup/db
BACKUP_REMOTE_LOCATION=something:somedir
DO_DB_BACKUP=1
DO_MEDIA_BACKUP=1

WATCHTOWER_NOTIFICATION_URL=CHANGEME_notification_or_empty
WATCHTOWER_NOTIFICATIONS_HOSTNAME=CHANGEME_identifier
```

Production checklist:

* Set `TAG=main` unless intentionally deploying another image tag.
* Set `DATA_DIR` to the persistent data directory.
* Replace all `CHANGEME` values.
* Use a strong `EVY_SECRET_KEY`.
* Use strong PostgreSQL credentials.
* Set `EVY_SITE_URL` to `https://<SERVER_NAME>`.
* Set `EVY_TALK_HOSTNAME` to `https://<SERVER_NAME>`.
* Set `EVY_ALLOWED_HOSTS` to the public domain.
* Configure SMTP settings.
* Configure backup settings if backups are enabled.
* Configure Watchtower notifications or disable Watchtower if not used.

Do not use `deployment/env.dev.sample` for production.

## Install nginx and certbot

Install nginx and certbot:

```bash
apt install nginx ssl-cert certbot python3-certbot-nginx
```

Enable nginx:

```bash
systemctl enable nginx
systemctl start nginx
```

Check nginx status:

```bash
systemctl status nginx
```

## Configure nginx

Copy the provided nginx site configuration:

```bash
cp /home/$USER/$DEPLOYMENT_NAME/eventyay/deployment/nginx/enext-direct /etc/nginx/sites-available/enext-direct
```

Edit the nginx site:

```bash
nano /etc/nginx/sites-available/enext-direct
```

Change at least:

* `SERVER_NAME`
* `<PATH_TO>` to the full path of `DATA_DIR`

The nginx configuration should proxy:

* regular application traffic to `web` on port `8000`
* websocket/ASGI traffic to `websocket` on port `8001`
* static and uploaded files to the configured data/static paths as defined in the nginx template

Enable the site:

```bash
ln -s /etc/nginx/sites-available/enext-direct /etc/nginx/sites-enabled/enext-direct
```

Remove the default site if it conflicts:

```bash
rm -f /etc/nginx/sites-enabled/default
```

Test nginx configuration:

```bash
nginx -t
```

Reload nginx:

```bash
systemctl reload nginx
```

## Configure SSL

Before requesting a certificate, ensure the DNS record for `SERVER_NAME` points to this server.

Check DNS from the server:

```bash
getent hosts $SERVER_NAME
```

Request and install the certificate:

```bash
certbot -m $MANAGEMENT_EMAIL --agree-tos --nginx
```

Check certificate status:

```bash
certbot certificates
```

Test automatic renewal:

```bash
certbot renew --dry-run
```

## Start Eventyay

Switch to the deployment user:

```bash
su - $USER
cd /home/$USER/$DEPLOYMENT_NAME
```

Pull images:

```bash
docker compose pull
```

Start the stack:

```bash
docker compose up -d
```

Check running services:

```bash
docker compose ps
```

Follow logs:

```bash
docker compose logs -f web
docker compose logs -f websocket
docker compose logs -f worker
docker compose logs -f beat
```

If migrations are not handled automatically by the container entrypoint, run them manually after confirming the current image behavior:

```bash
docker compose exec web python manage.py migrate
```

Create an admin user if needed:

```bash
docker compose exec web python manage.py create_admin_user
```

Collect static files if needed:

```bash
docker compose exec web python manage.py collectstatic --noinput
```

## Initial verification

Check the public site:

```bash
curl -I https://$SERVER_NAME/
```

Check the health endpoint:

```bash
curl -I https://$SERVER_NAME/healthcheck/
```

Check containers:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs --tail=100 web
docker compose logs --tail=100 websocket
docker compose logs --tail=100 worker
docker compose logs --tail=100 beat
docker compose logs --tail=100 db
docker compose logs --tail=100 redis
```

Verify in the browser:

* public start page loads
* login page loads
* admin interface loads
* static assets load correctly
* emails can be sent
* background tasks run
* websocket/video-related pages work if enabled

## Backups

Install backup tools:

```bash
apt install fdupes rclone
```

Backups should cover:

* PostgreSQL database
* uploaded media/data directory
* `.env`
* nginx site configuration
* rclone configuration

Install the backup scripts from:

```text
deployment/server-setup/scripts/
```

Copy the scripts to:

```text
/usr/local/bin/
```

Ensure they are executable:

```bash
chmod 0755 /usr/local/bin/<script-name>
```

Create log directory:

```bash
mkdir -p /var/log/fossasia
chown $USER:$USER /var/log/fossasia
```

Configure rclone for the deployment user:

```bash
su - $USER
mkdir -p ~/.config/rclone
chmod 700 ~/.config/rclone
```

Create `~/.config/rclone/rclone.conf`:

```ini
[backup_service]
type = b2
account = <ACCOUNT_ID>
key = <ACCOUNT_KEY>
```

Set permissions:

```bash
chmod 600 ~/.config/rclone/rclone.conf
```

Edit the crontab template:

```text
deployment/server-setup/crontab
```

Adjust:

* `.env` path
* healthcheck UUIDs
* backup schedule
* log paths

Install it as the deployment user crontab:

```bash
crontab deployment/server-setup/crontab
```

Check installed crontab:

```bash
crontab -l
```

A backup is only valid if restore has been tested. Periodically perform a test restore on a separate server or staging environment.

## Updating Eventyay

If Watchtower is enabled, container images may be updated automatically according to the Watchtower configuration.

Review whether automatic updates are appropriate for your production environment. Some operators may prefer manual updates after testing.

Manual update:

```bash
cd /home/$USER/$DEPLOYMENT_NAME
git -C eventyay fetch
git -C eventyay checkout main
git -C eventyay pull --ff-only

docker compose pull
docker compose up -d
docker compose ps
```

Follow logs after updating:

```bash
docker compose logs -f web
docker compose logs -f websocket
docker compose logs -f worker
docker compose logs -f beat
```

If needed, run migrations:

```bash
docker compose exec web python manage.py migrate
```

If needed, collect static files:

```bash
docker compose exec web python manage.py collectstatic --noinput
```

## Database and media migration

Use this section when moving an existing Eventyay deployment to a new server.

### On the old server

Stop application services:

```bash
cd /home/$USER/$DEPLOYMENT_NAME
docker compose down
```

Start only the database:

```bash
docker compose up -d db
```

Export PostgreSQL:

```bash
docker exec eventyay-next-db pg_dump -F tar -U "$POSTGRES_USER" "$POSTGRES_DB" > eventyay-db-$(date +%Y%m%d).tar
```

Archive uploaded data:

```bash
tar -C "$FULL_DATA_DIR" -czf eventyay-data-$(date +%Y%m%d).tar.gz data
```

Archive static files if required:

```bash
tar -C "$FULL_DATA_DIR" -czf eventyay-static-$(date +%Y%m%d).tar.gz static
```

Copy files to the new server:

```bash
rsync -av eventyay-db-*.tar eventyay-data-*.tar.gz eventyay-static-*.tar.gz user@new-server:/tmp/
```

### On the new server

Prepare the new deployment using the previous sections.

Start only the database:

```bash
cd /home/$USER/$DEPLOYMENT_NAME
docker compose up -d db
```

Restore PostgreSQL:

```bash
docker exec -i eventyay-next-db pg_restore --clean --verbose -U "$POSTGRES_USER" -d "$POSTGRES_DB" < /tmp/eventyay-db-YYYYMMDD.tar
```

Restore uploaded data:

```bash
tar -C "$FULL_DATA_DIR" -xzf /tmp/eventyay-data-YYYYMMDD.tar.gz
```

Restore static files if required:

```bash
tar -C "$FULL_DATA_DIR" -xzf /tmp/eventyay-static-YYYYMMDD.tar.gz
```

Fix ownership:

```bash
chown -R $USER:$USER "$FULL_DATA_DIR"
chown 100:101 "$FULL_DATA_DIR/data"
chmod ugo+rwx "$FULL_DATA_DIR/static"
```

Start the full stack:

```bash
docker compose up -d
```

Check logs and run verification:

```bash
docker compose ps
docker compose logs --tail=100 web
curl -I https://$SERVER_NAME/
curl -I https://$SERVER_NAME/healthcheck/
```

## Troubleshooting

### Check service status

```bash
docker compose ps
```

### Check logs

```bash
docker compose logs -f web
docker compose logs -f websocket
docker compose logs -f worker
docker compose logs -f beat
docker compose logs -f db
docker compose logs -f redis
```

### Check nginx

```bash
nginx -t
systemctl status nginx
journalctl -u nginx -n 100 --no-pager
```

### Check certificates

```bash
certbot certificates
certbot renew --dry-run
```

### 502 Bad Gateway

Check:

* `web` container is running
* `websocket` container is running if websocket route fails
* nginx upstream ports match Docker exposed ports
* firewall allows local proxy traffic
* `docker compose logs web`
* `docker compose logs websocket`

### Static files not loading

Check:

* nginx static path points to the correct `DATA_DIR/static`
* static directory is readable by nginx
* static files exist
* `collectstatic` has run if required
* browser receives CSS/JS with correct MIME type

Useful commands:

```bash
ls -la "$FULL_DATA_DIR/static"
docker compose exec web python manage.py collectstatic --noinput
systemctl reload nginx
```

### Database connection failure

Check:

* `db` container is running
* `.env` PostgreSQL values match
* `EVY_POSTGRES_HOST=eventyay-next-db`
* `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` match Eventyay settings
* PostgreSQL data directory permissions are correct

Useful commands:

```bash
docker compose logs -f db
docker compose exec db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

### Redis connection failure

Check:

* `redis` container is running
* Redis URL points to the Docker service name
* worker and beat can reach Redis

Useful commands:

```bash
docker compose logs -f redis
docker compose logs -f worker
docker compose logs -f beat
```

### Wrong host or domain errors

Check:

* `EVY_SITE_URL`
* `EVY_TALK_HOSTNAME`
* `EVY_ALLOWED_HOSTS`
* nginx `server_name`
* DNS record
* TLS certificate domain

### Email not sending

Check:

* SMTP host
* SMTP port
* TLS setting
* username and password
* sender address
* provider restrictions
* container logs

Useful command:

```bash
docker compose logs -f web
```

## Security notes

Do not use development settings in production.

Do not:

* use `deployment/env.dev.sample` for production
* run production with `EVY_DEBUG=1`
* commit `.env`
* expose PostgreSQL publicly
* expose Redis publicly
* use weak `EVY_SECRET_KEY`
* use default or weak PostgreSQL passwords
* deploy the `dev` image tag unless this is intentional
* enable automatic Watchtower updates without reviewing the operational risk

Recommended:

* restrict SSH access
* use SSH keys instead of password login
* keep Ubuntu packages updated
* keep Docker updated
* keep backups encrypted or access-controlled
* test restore procedures
* monitor disk usage
* monitor container logs
* monitor certificate renewal
* review `.env` permissions

Suggested `.env` permission:

```bash
chmod 600 /home/$USER/$DEPLOYMENT_NAME/.env
chown $USER:$USER /home/$USER/$DEPLOYMENT_NAME/.env
```

```
```
