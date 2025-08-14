#!/bin/sh
set -e

echo "--> Waiting for database at host 'db' on port 5432..."
while ! nc -z db 5432; do
  sleep 1
done
echo "--> Database is ready!"

echo "--> Applying database migrations..."
alembic upgrade head

echo "--> Starting application..."
exec "$@"