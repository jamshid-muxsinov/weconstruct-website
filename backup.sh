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

# --- ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: Безопасная загрузка переменных из .env ---
# Этот метод не исполняет файл, а читает его, что предотвращает ошибки синтаксиса.
if [ -f "$COMPOSE_PROJECT_DIR/.env" ]; then
    # Фильтруем .env файл, чтобы получить только нужные переменные,
    # и экспортируем их. `grep` ищет строки, начинающиеся с POSTGRES_USER= или POSTGRES_DB=
    export $(grep -E '^POSTGRES_USER=|^POSTGRES_DB=' "$COMPOSE_PROJECT_DIR/.env" | xargs)
fi

# Берём имя пользователя и базы из переменных окружения
DB_USER=${POSTGRES_USER}
DB_NAME=${POSTGRES_DB}

# Проверяем, что переменные определены
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "ERROR: POSTGRES_USER or POSTGRES_DB is not set or not found in your .env file."
  exit 1
fi

# Создаем директорию для бэкапов, если она не существует
mkdir -p "$BACKUP_DIR"

# Формируем имя файла с датой и временем
BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y-%m-%d_%H-%M-%S).dump"

echo "Starting backup of database '$DB_NAME' to $BACKUP_FILE..."

# Используем `docker compose` (с пробелом)
docker compose -f "$COMPOSE_PROJECT_DIR/docker-compose.yml" exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$BACKUP_FILE"

# Проверяем, что бэкап был создан
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