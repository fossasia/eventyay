#!/bin/sh

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

exec "$@"
