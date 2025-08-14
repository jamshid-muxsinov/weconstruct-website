# --- СТАДИЯ 1: Builder (Сборщик зависимостей) ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Устанавливаем системные утилиты, нужные для компиляции некоторых пакетов
RUN apt-get update && apt-get install -y gcc libpq-dev

# Копируем только файл с зависимостями, чтобы кэшировать этот слой
COPY requirements.txt .

# Создаем виртуальное окружение и устанавливаем зависимости в него
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt


# --- СТАДИЯ 2: Runner (Финальный образ) ---
FROM python:3.11-slim

# Устанавливаем ТОЛЬКО утилиты, нужные для работы entrypoint.sh
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем готовое виртуальное окружение из сборщика
COPY --from=builder /opt/venv /opt/venv

# Копируем весь исходный код проекта
COPY . .

# Копируем и делаем исполняемым наш скрипт
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Активируем venv для всех последующих команд
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]