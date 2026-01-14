# pull official base image
# This is a copy of app/Dockerfile for Render.com compatibility
# Render expects Dockerfile at repository root
# For all other platforms, use app/Dockerfile
# Keep both files in sync when making changes

FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install system dependencies
RUN apt-get update && apt-get install -y wget gnupg
# Repo for newer NodeJS
RUN wget -qO- https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list
RUN apt-get update && apt-get install --no-install-recommends -y netcat-traditional git build-essential gettext make nodejs

# copy project files
COPY . .

# install dependencies
RUN uv sync --all-extras --all-groups

# copy entrypoint.sh
COPY ./entrypoint.sh .
RUN sed -i 's/\r$//g' /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# Expose virtual env
ENV VIRTUAL_ENV=/usr/src/app/.venv
ENV PATH="/usr/src/app/.venv/bin:$PATH"

# Run npm stuff
RUN make npminstall

# Build webapp
RUN make webappbuild

# esbuild needed by Django-Compressor
RUN npm install -g esbuild

# Generate i18n JavaScript files FIRST
RUN EVY_SECRET_KEY=build_dummy EVY_REDIS_URL=redis://localhost:6379/0 python manage.py compilejsi18n
# Generate static files (with dummy secrets for build time)
RUN EVY_SECRET_KEY=build_dummy EVY_REDIS_URL=redis://localhost:6379/0 python manage.py collectstatic --noinput
# Run compress with production settings to generate correct manifest
RUN EVY_SECRET_KEY=build_dummy \
    EVY_REDIS_URL=redis://localhost:6379/0 \
    EVY_RUNNING_ENVIRONMENT=production \
    EVY_SITE_URL=https://eventyay-next-web-287238307795.us-central1.run.app \
    python manage.py compress --force

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
