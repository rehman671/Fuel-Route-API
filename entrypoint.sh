#!/bin/bash
set -e

echo "==> Waiting for PostgreSQL..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        host=os.environ['POSTGRES_HOST'],
        port=os.environ.get('POSTGRES_PORT', '5432'),
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
    echo "   postgres not ready — retrying in 2s..."
    sleep 2
done
echo "   PostgreSQL is up."

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Seeding app constants..."
python manage.py init_constants

echo "==> Importing fuel stations (skip if already done)..."
python manage.py import_fuel_stations --skip-existing

echo "==> Running tests..."
python manage.py test --noinput

echo "==> Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
