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
