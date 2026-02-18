# Development Setup

Локальная разработка ведется через базовый `docker-compose.yml` + автоматический `docker-compose.override.yml`.

## Быстрый старт

```bash
cd /home/tasheet/development/sa_fastapi
docker compose up
```

## URL

- Admin: http://localhost:8000
- Site: http://localhost:8001/uz

## Основные команды

```bash
# Запуск
docker compose up

# Остановка
docker compose down

# Логи
docker compose logs -f admin
docker compose logs -f site

# Миграции
docker compose exec admin alembic upgrade head

# Создать миграцию
docker compose exec admin alembic revision --autogenerate -m "message"
```

## Live reload

`docker-compose.override.yml` запускает `uvicorn --reload`, поэтому изменения в `src/` применяются без пересборки образа.

## Важно

- Production-файлы не менять: `docker-compose.yml`, `Dockerfile`, `entrypoint.sh`, `.env`.
- Не коммитить локальные секреты.
- Перед деплоем использовать `PRODUCTION_CHECKLIST.md`.
