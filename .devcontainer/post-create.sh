#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH="/app"
BACKEND_PATH="/app/backend"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-backend_db}"
DB_USER="${DB_USER:-backend_user}"
DB_PASS="${DB_PASSWORD:-backend_password}"

echo "Setting up Django backend with task queue..."

# Wait for Postgres to be ready
echo "Waiting for Postgres at ${DB_HOST}:${DB_PORT}..."
for i in {1..60}; do
  if nc -z "$DB_HOST" "$DB_PORT" >/dev/null 2>&1; then
    echo "Postgres is ready."
    break
  fi
  sleep 1
  if [[ $i -eq 60 ]]; then
    echo "Postgres did not become ready in time."
    exit 1
  fi
done

# Navigate to backend directory
cd "$BACKEND_PATH"

# Make sure Python dependencies are installed
echo "Installing Django backend dependencies..."
pip install -e ".[dev]"

# Create and run Django migrations
echo "Creating Django migrations..."
python manage.py makemigrations core
python manage.py makemigrations task_queue

echo "Running Django migrations..."
python manage.py migrate

# Create superuser if it doesn't exist
echo "Creating Django superuser (if not exists)..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: admin/admin')
else:
    print('Superuser already exists')
" || true


echo "Seeding regexes..."
python manage.py seed_regexes --update