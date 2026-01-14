#!/bin/sh
set -e

echo "Entrypoint script starting..."
echo "Arguments passed: '$@'"

echo "Waiting for postgres..."

while ! nc -z ${EVY_POSTGRES_HOST:-$POSTGRES_HOST} ${EVY_POSTGRES_PORT:-$POSTGRES_PORT}; do
  sleep 0.1
done

echo "PostgreSQL started"

# Only run migrations if we are the web entrypoint (heuristic: check for gunicorn)
# actually, it's safer to always run them for now, but logged
echo "Running migrations..."
python manage.py migrate
echo "Migrations completed."

echo "Executing final command: $@"

if [ -z "$1" ]; then
    echo "No arguments passed. Defaulting to gunicorn web server..."
    # Use explicit bind to 0.0.0.0 and PORT env var
    exec gunicorn eventyay.config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
else
    exec "$@"
fi
