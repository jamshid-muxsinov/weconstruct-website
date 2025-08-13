#!/bin/bash

# Ждем, пока база данных будет готова (опционально, но хорошая практика)
# echo "Waiting for postgres..."
# while ! nc -z db 5432; do
#   sleep 0.1
# done
# echo "PostgreSQL started"

echo "Waiting for database to be ready..."
python - <<'PYWAIT'
import asyncio
import time
import sys
from src.core.db import check_db_connection

async def main():
    for attempt in range(30):
        ok = await check_db_connection()
        if ok:
            print("Database is ready")
            return
        print("Database not ready yet, retrying...", attempt + 1)
        await asyncio.sleep(2)
    print("Database is not ready after retries", file=sys.stderr)
    sys.exit(1)

asyncio.run(main())
PYWAIT

# Применяем миграции базы данных
echo "Applying database migrations..."
alembic upgrade head

# Запускаем основное приложение (используем exec, чтобы uvicorn стал главным процессом)
echo "Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000