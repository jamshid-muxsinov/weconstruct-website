#!/bin/sh

# Выходить из скрипта при любой ошибке
set -e

# --- Ожидание готовности базы данных (УЛУЧШЕННАЯ ВЕРСИЯ) ---
# Извлекаем часть 'хост:порт' из URL
HOST_PORT_PART=$(echo "$DATABASE_URL" | cut -d'@' -f2 | cut -d'/' -f1)

# Из этой части извлекаем хост и порт
DB_HOST=$(echo "$HOST_PORT_PART" | cut -d':' -f1)
DB_PORT=$(echo "$HOST_PORT_PART" | cut -d':' -f2)

echo "--> Waiting for database at host '$DB_HOST' on port '$DB_PORT'..."

# Используем netcat для проверки, доступен ли порт
while ! nc -z "$DB_HOST" "$DB_PORT"; do
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