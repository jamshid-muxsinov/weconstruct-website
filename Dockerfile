# Стадия 1: Сборка фронтенда
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Стадия 2: Основное Python-приложение
FROM python:3.11-slim
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y curl netcat-openbsd --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего кода проекта
COPY . .

# Копирование собранного фронтенда из первой стадии
COPY --from=builder /app/src/static/dist /app/src/static/dist

# --- КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ ЗДЕСЬ ---
# 1. Устанавливаем PYTHONPATH, чтобы Python всегда видел папку /app как корень
ENV PYTHONPATH=/app

# 2. Убеждаемся, что entrypoint исполняемый (на всякий случай)
RUN chmod +x /app/entrypoint.sh
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

ENTRYPOINT ["/app/entrypoint.sh"]

# CMD больше не нужен, так как он полностью переопределяется в docker-compose.yml
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "src.main:site_app"]