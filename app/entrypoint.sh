#!/bin/sh

echo "Waiting for postgres..."

while ! nc -z ${EVY_POSTGRES_HOST:-$POSTGRES_HOST} ${EVY_POSTGRES_PORT:-$POSTGRES_PORT}; do
  sleep 0.1
done

echo "PostgreSQL started"

python manage.py migrate

exec "$@"
