#!/bin/bash

# --- НАСТРОЙКИ ---
# Абсолютный путь к корневой директории вашего проекта.
COMPOSE_PROJECT_DIR="/home/weconstruct-uz/weconstruct-website"

# Имя сервиса БД из docker-compose.yml (скорее всего, 'db')
DB_SERVICE="db"

# Директория для хранения бэкапов на хост-машине.
# Рекомендуется вынести её за пределы папки проекта для безопасности.
BACKUP_DIR="/var/backups/weconstruct_db"

# Устанавливаем переменные окружения, если у вас есть .env файл
if [ -f "$COMPOSE_PROJECT_DIR/.env" ]; then
  # Используем grep, чтобы избежать проблем с комментариями и пустыми строками
  export $(grep -vE '^#|^$' "$COMPOSE_PROJECT_DIR/.env" | xargs)
fi

# Берём имя пользователя и базы из переменных окружения (которые могли быть загружены из .env)
# Эти переменные (POSTGRES_USER, POSTGRES_DB) обычно определяются в docker-compose.yml
DB_USER=${POSTGRES_USER}
DB_NAME=${POSTGRES_DB}

# Проверяем, что переменные определены
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "ERROR: POSTGRES_USER or POSTGRES_DB is not set. Please check your .env file or docker-compose configuration."
  exit 1
fi

# Создаем директорию для бэкапов, если она не существует (с правами суперпользователя, если нужно)
# Это нужно выполнить один раз вручную: sudo mkdir -p /var/backups/weconstruct_db && sudo chown $USER:$USER /var/backups/weconstruct_db
mkdir -p "$BACKUP_DIR"

# Формируем имя файла с датой и временем
BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y-%m-%d_%H-%M-%S).dump"

echo "Starting backup of database '$DB_NAME' to $BACKUP_FILE..."

# Выполняем команду pg_dump через docker-compose.
# -f явно указывает путь к файлу, что делает скрипт надежнее.
docker-compose -f "$COMPOSE_PROJECT_DIR/docker-compose.yml" exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$BACKUP_FILE"

# Проверяем, что бэкап был создан
if [ ${PIPESTATUS[0]} -eq 0 ]; then
  echo "Backup successfully created: $BACKUP_FILE"
else
  echo "ERROR: Backup failed!"
  # Удаляем пустой файл, если pg_dump завершился с ошибкой
  rm -f "$BACKUP_FILE"
  exit 1
fi

# Удаляем старые бэкапы (старше 7 дней)
echo "Cleaning up old backups (older than 7 days)..."
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +7 -exec rm {} \;
echo "Cleanup complete."