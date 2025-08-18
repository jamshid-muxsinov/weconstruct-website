#!/bin/bash
set -e # Останавливать скрипт при любой ошибке

# --- НАСТРОЙКИ ---
# Абсолютный путь к корневой директории вашего проекта.
COMPOSE_PROJECT_DIR="/home/weconstruct-uz/weconstruct-website"

# Имя сервиса БД из docker-compose.yml
DB_SERVICE="db"

# Директория для хранения бэкапов на хост-машине.
BACKUP_DIR="/var/backups/weconstruct_db"
# --- КОНЕЦ НАСТРОЕК ---

# --- ИСПРАВЛЕНИЕ №1: Надежная загрузка .env файла ---
# Этот метод корректно работает со сложными значениями (URL, пробелы и т.д.)
if [ -f "$COMPOSE_PROJECT_DIR/.env" ]; then
  set -o allexport
  source "$COMPOSE_PROJECT_DIR/.env"
  set +o allexport
fi

# Берём имя пользователя и базы из переменных окружения
DB_USER=${POSTGRES_USER}
DB_NAME=${POSTGRES_DB}

# Проверяем, что переменные определены
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "ERROR: POSTGRES_USER or POSTGRES_DB is not set. Please check your .env file."
  exit 1
fi

# Создаем директорию для бэкапов, если она не существует
mkdir -p "$BACKUP_DIR"

# Формируем имя файла с датой и временем
BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y-%m-%d_%H-%M-%S).dump"

echo "Starting backup of database '$DB_NAME' to $BACKUP_FILE..."

# --- ИСПРАВЛЕНИЕ №2: Используем `docker compose` (с пробелом) ---
docker compose -f "$COMPOSE_PROJECT_DIR/docker-compose.yml" exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$BACKUP_FILE"

# Проверяем, что бэкап был создан
# PIPESTATUS[0] проверяет код завершения именно команды pg_dump, а не `>`
if [ ${PIPESTATUS[0]} -eq 0 ]; then
  echo "Backup successfully created: $BACKUP_FILE"
else
  echo "ERROR: Backup failed!"
  # Удаляем пустой или поврежденный файл, если pg_dump завершился с ошибкой
  rm -f "$BACKUP_FILE"
  exit 1
fi

# Удаляем старые бэкапы (старше 7 дней)
echo "Cleaning up old backups (older than 7 days)..."
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +7 -exec rm {} \;
echo "Cleanup complete."