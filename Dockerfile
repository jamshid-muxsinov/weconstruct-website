# Стадия 1: Сборка фронтенда с оптимизацией кэша
FROM node:18-alpine AS builder
WORKDIR /app
# Сначала копируем только package.json и устанавливаем зависимости
COPY package*.json ./
RUN npm install
# Теперь копируем весь остальной код для сборки
COPY . .
RUN npm run build

# Стадия 2: Основное Python-приложение
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Переменные окружения для Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y curl netcat-openbsd --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python-зависимостей с оптимизацией кэша
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем только необходимые для работы приложения папки и файлы
COPY alembic ./alembic/
COPY alembic.ini .
COPY src ./src/
COPY entrypoint.sh .

# Копирование собранного фронтенда из первой стадии
COPY --from=builder /app/src/static/dist /app/src/static/dist/

# Делаем entrypoint исполняемым
RUN chmod +x /app/entrypoint.sh

# Запускаем скрипт-обертку
ENTRYPOINT ["/app/entrypoint.sh"]

# Команда по умолчанию (будет переопределена в docker-compose, но полезна для standalone запуска)
CMD ["gunicorn", "--chdir", "/app/src", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:site_app"]