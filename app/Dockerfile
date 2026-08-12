# syntax=docker/dockerfile:1
###########
# BUILDER #
###########

# pull official base image
FROM python:3.12-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install system dependencies (build tools needed here)
RUN apt-get update && apt-get install -y wget gnupg

# Repo for newer NodeJS
RUN wget -qO- https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list

RUN apt-get update && apt-get install --no-install-recommends -y \
    netcat-traditional \
    git \
    build-essential \
    gettext \
    make \
    nodejs

# copy project files
COPY . .

# install dependencies (using build tools)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-extras --all-groups

# Read EVY_NPM_DEV from repo-root .env.dev (via compose additional_contexts).
# When set to 1, skip make npminstall — Vite HMR installs deps at runtime.
RUN --mount=type=bind,from=project_root,target=/project_root,ro \
    if [ -f /project_root/.env.dev ] && grep -qE '^[[:space:]]*EVY_NPM_DEV=1([[:space:]]|#|$)' /project_root/.env.dev; then \
      echo "EVY_NPM_DEV=1: skipping make npminstall (Vite HMR will install deps at runtime)"; \
    else \
      make npminstall; \
    fi

# Pre-build static.dist so the image ships with Django/static assets (and Vite
# manifests when npminstall ran above).
RUN uv run python manage.py collectstatic --noinput


###########
# RUNTIME #
###########

# pull official base image
FROM python:3.12-slim-trixie

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install ONLY runtime dependencies (no build tools!)
RUN apt-get update && apt-get install -y wget gnupg

# NodeJS runtime (without build tools)
RUN wget -qO- https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list

RUN apt-get update && apt-get install --no-install-recommends -y \
    netcat-traditional \
    nodejs \
    make \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# esbuild needed by Django-Compressor
RUN npm install -g esbuild

# Copy application code from builder (includes .venv and entrypoint.sh)
COPY --from=builder /usr/src/app /usr/src/app

# Normalize line endings and set executable bit AFTER the bulk copy
RUN sed -i 's/\r$//g' /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# Copy uv package manager to final stage for runtime plugin installation
COPY --from=builder /bin/uv /bin/uv

# Expose virtual env
ENV VIRTUAL_ENV=/usr/src/app/.venv
ENV PATH="/usr/src/app/.venv/bin:$PATH"

# Create .secrets to suppress warnings about missing directory
RUN mkdir -p /usr/src/app/.secrets

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
