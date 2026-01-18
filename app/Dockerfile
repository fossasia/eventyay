# pull official base image
FROM python:3.11-slim-bookworm
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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-extras --all-groups

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

# Create .secrets to suppress warnings about missing directory
RUN mkdir -p $APP_HOME/.secrets

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
