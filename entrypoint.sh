#!/bin/sh

# Выходить из скрипта при любой ошибке
set -e

# --- Ожидание готовности базы данных ---
# Извлекаем хост и порт из DATABASE_URL
DB_HOST=$(echo $DATABASE_URL | cut -d'@' -f2 | cut -d':' -f1)
DB_PORT=$(echo $DATABASE_URL | cut -d':' -f3 | cut -d'/' -f1)

echo "--> Waiting for database at host '$DB_HOST' on port $DB_PORT..."

# Используем netcat для проверки, доступен ли порт
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "--> Database is ready!"

# --- Применение миграций Alembic ---
echo "--> Applying database migrations..."
alembic upgrade head

echo "--> Migrations applied!"
echo "--> Starting application..."

# --- Запуск основной команды ---
# exec "$@" выполняет команду, переданную в entrypoint
# (в нашем случае, это команда gunicorn из docker-compose.yml)
exec "$@"