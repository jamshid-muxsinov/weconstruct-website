# WeConstruct CRM

FastAPI-сервис для construction-операций и публичной витрины: проекты, Kanban,
клиенты, двуязычные маршруты, кэширование, rate limiting и интеграции Telegram/
Google Sheets.

## Запуск

Для локального запуска с зависимостями проекта:

```bash
cp .env.example .env
docker compose up -d --build
```

Проверка доступности и тесты:

```bash
docker compose ps
pytest -q
```

Есть также host-вариант: `python -m venv .venv`, `pip install -r requirements.txt`,
затем команда запуска из `entrypoint.sh`. Секреты и `credentials.json` не должны
попадать в Git.

## Стек

FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Nginx, Playwright.
