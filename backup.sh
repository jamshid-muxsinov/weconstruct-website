#!/bin/bash
set -e # Останавливать скрипт при любой ошибке

# --- НАСТРОЙКИ ---
COMPOSE_PROJECT_DIR="/home/weconstruct-uz/weconstruct-website"
DB_SERVICE="db"
BACKUP_DIR="/var/backups/weconstruct_db"
# --- КОНЕЦ НАСТРОЕК ---

if [ -f "$COMPOSE_PROJECT_DIR/.env" ]; then
    export $(grep -E '^POSTGRES_USER=|^POSTGRES_DB=' "$COMPOSE_PROJECT_DIR/.env" | xargs)
fi

DB_USER=${POSTGRES_USER}
DB_NAME=${POSTGRES_DB}

if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "ERROR: POSTGRES_USER or POSTGRES_DB is not set in .env file."
  exit 1
fi

# Создаем директорию с правами root, если ее нет
sudo mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y-%m-%d_%H-%M-%S).dump"

echo "Starting backup of database '$DB_NAME' to $BACKUP_FILE..."

# Команда docker compose должна выполняться от пользователя с доступом к Docker
docker compose -f "$COMPOSE_PROJECT_DIR/docker-compose.yml" exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$BACKUP_FILE"

if [ ${PIPESTATUS[0]} -eq 0 ]; then
  echo "Backup successfully created: $BACKUP_FILE"
else
  echo "ERROR: Backup failed!"
  sudo rm -f "$BACKUP_FILE"
  exit 1
fi

# Используем sudo для удаления и выводим список удаляемых файлов
echo "Cleaning up old backups (older than 7 days)..."
# Сначала находим файлы, чтобы убедиться, что команда работает
OLD_BACKUPS=$(find "$BACKUP_DIR" -type f -name "*.dump" -mtime +7)

if [ -n "$OLD_BACKUPS" ]; then
  echo "Found old backups to delete:"
  echo "$OLD_BACKUPS"
  # Удаляем найденные файлы с помощью xargs и sudo
  echo "$OLD_BACKUPS" | xargs sudo rm -v
  echo "Old backups deleted."
else
  echo "No old backups found to delete."
fi

echo "Cleanup complete."