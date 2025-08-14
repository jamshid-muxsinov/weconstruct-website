# --- СТАДИЯ 1: Builder (Сборщик зависимостей) ---
# Эта стадия нужна, чтобы установить все зависимости, включая те, что требуют компиляции.
FROM python:3.11-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y curl 

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Копируем только файл с зависимостями. Docker будет кэшировать этот слой
# и не будет переустанавливать всё заново, если requirements.txt не изменился.
COPY requirements.txt .

# Создаем виртуальное окружение. Это хорошая практика даже внутри Docker.
RUN python -m venv /opt/venv
# Активируем venv для всех последующих команд в этой стадии
ENV PATH="/opt/venv/bin:$PATH"

# Устанавливаем зависимости в виртуальное окружение
RUN pip install --no-cache-dir -r requirements.txt


# --- СТАДИЯ 2: Runner (Финальный образ) ---
# Эта стадия создает чистый, легковесный образ для запуска приложения.
FROM python:3.11-slim

# Устанавливаем ТОЛЬКО те утилиты, которые нужны для работы entrypoint.sh.
# dos2unix добавлен как дополнительная гарантия исправления окончаний строк.
RUN apt-get update && apt-get install -y netcat-openbsd dos2unix && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем готовое виртуальное окружение со всеми установленными зависимостями из сборщика
COPY --from=builder /opt/venv /opt/venv

# Копируем весь исходный код нашего проекта
COPY . .

# Копируем и делаем исполняемым наш скрипт
COPY entrypoint.sh /app/entrypoint.sh

# --- НАДЕЖНОЕ ИСПРАВЛЕНИЕ ОШИБКИ "exec format error" ---
# Принудительно конвертируем окончания строк в Unix-формат (LF)
RUN dos2unix /app/entrypoint.sh
# Даем скрипту права на выполнение
RUN chmod +x /app/entrypoint.sh
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

# Глобально активируем venv для всех последующих команд (ENTRYPOINT, CMD)
ENV PATH="/opt/venv/bin:$PATH"

# Сообщаем Docker, что приложение будет слушать этот порт
EXPOSE 8000

# Указываем, что наш скрипт будет точкой входа для контейнера
ENTRYPOINT ["/app/entrypoint.sh"]

# Команда по умолчанию, которая будет передана в entrypoint.sh в качестве аргументов "$@"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]