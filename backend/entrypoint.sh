#!/bin/sh
# ==============================================================================
# Entrypoint — FamilyHostel backend container
# Waits for Postgres, runs migrations, then starts gunicorn.
# ==============================================================================
set -e

echo "🔄 Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

# Poll until PostgreSQL accepts connections (max 30 seconds)
retries=0
max_retries=30
until python -c "
import socket, sys
try:
    s = socket.create_connection(('${DB_HOST}', int('${DB_PORT}')), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    retries=$((retries + 1))
    if [ "$retries" -ge "$max_retries" ]; then
        echo "❌ PostgreSQL not available after ${max_retries}s — aborting."
        exit 1
    fi
    echo "   ⏳ Attempt ${retries}/${max_retries}..."
    sleep 1
done

echo "✅ PostgreSQL is ready."

echo "🔄 Running database migrations..."
python manage.py migrate --noinput

echo "🔄 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Gunicorn (ASGI + Uvicorn workers)..."
exec gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
