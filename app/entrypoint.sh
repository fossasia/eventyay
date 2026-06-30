#!/bin/bash

echo "Waiting for postgres..."

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do [ "${c:=0}" -gt 200 ] && echo "PostgreSQL connection timeout" && exit 1; sleep 0.1; c=$((c+1)); done

echo "PostgreSQL started"

# Install local plugins if mapped
VENV_PYTHON="${VIRTUAL_ENV:-/usr/src/app/.venv}/bin/python"
if [ -d /usr/src/plugins ]; then
  mkdir -p /tmp/eventyay-plugin-stamps
  for dir in /usr/src/plugins/*/; do
    if [ -f "$dir/setup.py" ] || [ -f "$dir/pyproject.toml" ]; then
      plugin_name=$(basename "$dir")
      stamp_file="/tmp/eventyay-plugin-stamps/${plugin_name}.installed"
      
      # Check if stamp file is older than setup.py or pyproject.toml
      needs_install=0
      if [ ! -f "$stamp_file" ]; then
        needs_install=1
      elif [ -f "$dir/setup.py" ] && [ "$dir/setup.py" -nt "$stamp_file" ]; then
        needs_install=1
      elif [ -f "$dir/pyproject.toml" ] && [ "$dir/pyproject.toml" -nt "$stamp_file" ]; then
        needs_install=1
      fi

      if [ "$needs_install" = "1" ]; then
        echo "Installing local plugin in editable mode: $dir"
        uv pip install --python "$VENV_PYTHON" -e "$dir" && touch "$stamp_file"
      else
        echo "Local plugin already installed, skipping: $dir"
      fi
    fi
  done
fi

python manage.py migrate

# Start Vite dev servers for live frontend development when EVY_NPM_DEV=1
if [ "$EVY_NPM_DEV" = "1" ]; then
  echo "EVY_NPM_DEV=1 — starting Vite dev servers for live frontend development..."

  WEBAPP_DIR=/usr/src/app/eventyay/webapp

  start_vite() {
    local app=$1 port=$2 config_arg=$3
    local app_dir="$WEBAPP_DIR/$app"
    if [ ! -d "$app_dir" ]; then
      echo "WARNING: $app_dir does not exist, skipping."
      return
    fi
    echo "Starting $app Vite dev server on port $port..."
    cd "$app_dir" || return
    if [ -d "node_modules" ]; then
      echo "  node_modules exists, skipping npm ci for $app"
    else
      echo "  Running npm ci for $app..."
      npm ci || { echo "ERROR: npm ci failed for $app"; return; }
    fi
    npx vite --host 0.0.0.0 --port "$port" $config_arg 2>&1 &
    local vite_pid=$!
    sleep 2
    if kill -0 "$vite_pid" 2>/dev/null; then
      echo "  $app Vite dev server running (PID: $vite_pid)"
    else
      echo "  ERROR: $app Vite dev server failed to start (check output above)"
    fi
  }

  start_vite "schedule-editor" 8080 ""
  start_vite "video" 8880 ""
  start_vite "schedule" 8082 "--config vite.config.wc.js"

  cd /usr/src/app
  echo "All Vite dev servers started."
fi

exec "$@"
