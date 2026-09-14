#!/bin/bash

echo "Waiting for postgres..."

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do [ "${c:=0}" -gt 200 ] && echo "PostgreSQL connection timeout" && exit 1; sleep 0.1; c=$((c+1)); done

echo "PostgreSQL started"

VENV_PYTHON="${VIRTUAL_ENV:-/usr/src/app/.venv}/bin/python"

# Install or sync local plugins in development
if [ "$EVY_RUNNING_ENVIRONMENT" = "development" ]; then
  PLUGIN_DEV_MODE="${EVY_PLUGIN_DEV_MODE:-${PLUGIN_DEV_MODE:-1}}"

  if [ "$PLUGIN_DEV_MODE" = "1" ] && [ -d /usr/src/plugins ]; then
    mkdir -p /tmp/eventyay-plugin-stamps
    for dir in /usr/src/plugins/*/; do
      [ -d "$dir" ] || continue
      if [ -f "$dir/setup.py" ] || [ -f "$dir/pyproject.toml" ]; then
        plugin_name=$(basename "$dir")
        stamp_file="/tmp/eventyay-plugin-stamps/${plugin_name}.installed"
        
        # Check if stamp file is missing or older than config files
        if [ ! -f "$stamp_file" ] || \
           { [ -f "$dir/setup.py" ] && [ "$dir/setup.py" -nt "$stamp_file" ]; } || \
           { [ -f "$dir/pyproject.toml" ] && [ "$dir/pyproject.toml" -nt "$stamp_file" ]; }; then
          echo "Installing local plugin in editable mode: $dir"
          uv pip install --python "$VENV_PYTHON" -e "$dir" && touch "$stamp_file"
        else
          echo "Local plugin already installed, skipping: $dir"
        fi
      fi
    done
  elif [ "$PLUGIN_DEV_MODE" = "0" ] && [ -d /tmp/eventyay-plugin-stamps ]; then
    echo "PLUGIN_DEV_MODE=0: Restoring package dependencies from lockfile..."
    (cd /usr/src/app && uv sync --all-extras --all-groups)
    rm -rf /tmp/eventyay-plugin-stamps
  fi
fi

# If Celery process (worker or beat), skip web-only initialization steps
if [ "$1" = "celery" ]; then
  exec "$@"
fi

python manage.py migrate
python manage.py compilemessages -i .venv
find /usr/src/app/eventyay/locale -name "*.mo" -exec sh -c 'chown --reference="${1%.mo}.po" "$1" 2>/dev/null || true' _ {} \;

# Web-only development initialization
if [ "$EVY_RUNNING_ENVIRONMENT" = "development" ]; then
  # 1. Video test servers
  if [ "$VIDEO_SERVER_TEST_MODE" = "1" ]; then
    echo "VIDEO_SERVER_TEST_MODE=1 — enabling local video test servers..."
    python manage.py sync_video_test_servers --enable
  elif [ "$VIDEO_SERVER_TEST_MODE" = "0" ]; then
    echo "VIDEO_SERVER_TEST_MODE=0 — deactivating local video test servers..."
    python manage.py sync_video_test_servers --disable
  fi

  # 2. Vite dev servers
  if [ "$EVY_NPM_DEV" = "1" ]; then
    case "$*" in
      *runserver*)
        echo "EVY_NPM_DEV=1 — starting Vite dev servers for live frontend development..."
        WEBAPP_DIR=/usr/src/app/eventyay/webapp

        start_vite() {
          local app=$1 port=$2 app_dir="${3:-$WEBAPP_DIR/$1}"
          if [ ! -f "$app_dir/package.json" ]; then
            echo "WARNING: $app_dir/package.json missing, skipping $app."
            return
          fi
          echo "Starting $app Vite dev server on port $port..."
          cd "$app_dir" || return
          if [ ! -d "node_modules/.bin" ]; then
            echo "  Running npm ci for $app..."
            npm ci || { echo "ERROR: npm ci failed for $app"; return; }
          else
            echo "  node_modules exists and is populated, skipping npm ci for $app"
          fi
          npx vite --host 0.0.0.0 --port "$port" 2>&1 &
          local vite_pid=$!
          sleep 2
          if kill -0 "$vite_pid" 2>/dev/null; then
            echo "  $app Vite dev server running (PID: $vite_pid)"
          else
            echo "  ERROR: $app Vite dev server failed to start (check output above)"
          fi
        }

        start_vite "schedule-editor" 8080
        start_vite "video" 8880
        start_vite "schedule" 8082
        if [ "$PLUGIN_DEV_MODE" = "1" ]; then
          start_vite "eventyay-checkin" 8085 "/usr/src/plugins/eventyay-checkin"
        else
          echo "PLUGIN_DEV_MODE!=1 — skipping Vite dev server for eventyay-checkin"
        fi

        cd /usr/src/app
        echo "All Vite dev servers started."
        ;;
    esac
  fi
fi

exec "$@"
