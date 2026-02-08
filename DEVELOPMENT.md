# 🚀 ЛОКАЛЬНАЯ РАЗРАБОТКА

## Быстрый старт

### 1. Первый запуск (с инициализацией БД)

```bash
# Перейди в корневую папку проекта
cd /home/tasheet/development/sa_fastapi

# Запусти Docker Compose (автоматически применится override)
docker compose up -d

# Проверь статус
docker compose ps
```

**Что происходит:**
- PostgreSQL инициализируется с нуля
- Redis стартует
- Python dependencies устанавливаются из `requirements.txt` (если образ еще не собран)
- Применяются миграции Alembic (`alembic upgrade head`)
- Создается администратор: `admin` / `admin123`
- Uvicorn стартует с режимом `--reload` (автоперезагрузка при изменении кода)

### 2. Обычный запуск (когда БД уже инициализирована)

```bash
# Просто запусти контейнеры
docker compose up
```

**Все контейнеры должны быть в состоянии `running`:**
```
NAME                COMMAND                  SERVICE     STATUS      PORTS
sa_fastapi-admin-1    "python -m uvicorn..."   admin       running     0.0.0.0:8000->8000/tcp
sa_fastapi-site-1     "python -m uvicorn..."   site        running     0.0.0.0:8001->8000/tcp
sa_fastapi-db-1       "docker-entrypoint.s…"   db          running     5432/tcp
sa_fastapi-redis-1    "redis-server"           redis       running     6379/tcp
sa_fastapi-nginx-1    "/docker-entrypoint.…"   nginx       running     0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

### 3. Доступ к приложению

| Сервис | URL | Описание |
|--------|-----|---------|
| **Admin Panel** | http://localhost:8000 | CRM админ-панель |
| **Site (Shop)** | http://localhost:8001 | Публичный сайт |
| **Nginx** (production-like) | http://localhost | Проксирует на site/admin (если нужен) |

**Логины:**
- Admin: `admin` / `admin123`

---

## 🔥 Как разрабатывать

### Изменение Python-кода

```bash
# 1. Отредактируй файл в src/
vim src/pages/shop_pages.py

# 2. Сохрани файл
# 3. Uvicorn автоматически перезагрузится (смотри логи)
docker compose logs -f admin  # или site
```

**Тебе НЕ нужно:**
- ❌ Останавливать контейнер
- ❌ Пересобирать образ (`docker compose build`)
- ❌ Перезапускать контейнер

Просто сохрани файл → логи покажут перезагрузку → F5 в браузере!

### Изменение статики (CSS/JS)

⚠️ **ВАЖНО:** Если ты меняешь фронтенд (`src/static/`), нужна сборка npm:

```bash
# 1. Если используешь Node локально:
npm run build

# 2. ИЛИ внутри контейнера (если Node не установлен локально):
docker compose exec admin npm run build
# или если npm в отдельном контейнере:
docker run -v $(pwd):/app -w /app node:18-alpine npm run build
```

Потом F5 в браузере.

Если статика не обновляется, очистить кэш браузера (Ctrl+Shift+Del).

### Изменение конфига БД или моделей

```bash
# 1. Отредактируй модель в src/models/
vim src/models/shop_models.py

# 2. Создай миграцию
docker compose exec admin alembic revision --autogenerate -m "describe your changes"

# 3. Проверь файл миграции (обычно в alembic/versions/)
vim alembic/versions/*_describe_your_changes.py

# 4. Примени миграцию
docker compose exec admin alembic upgrade head

# 5. Перезагрузи контейнер (из-за изменения моделей)
docker compose restart admin site
```

### Изменение .env переменных

```bash
# 1. Отредактируй .env.dev или .env (для локального override)
vim .env

# 2. Перезагрузи контейнеры
docker compose restart admin site
```

### Просмотр логов

```bash
# Все контейнеры
docker compose logs -f

# Только admin
docker compose logs -f admin

# Только site
docker compose logs -f site

# Только последние 50 строк
docker compose logs --tail=50 admin
```

---

## 🛑 Остановка и очистка

### Просто остановить контейнеры (данные БД сохранятся)

```bash
docker compose down
```

### Полная очистка (⚠️ потеряются ВСЕ данные в БД)

```bash
# Остановить и удалить volume с БД
docker compose down -v

# Потом снова запустить с нуля
docker compose up
```

### Остановить конкретный контейнер

```bash
docker compose stop admin
docker compose stop site
```

---

## 🐛 Отладка

### Если контейнер крашится при запуске

```bash
# 1. Посмотри логи
docker compose logs admin

# 2. Проверь переменные .env
cat .env

# 3. Проверь БД доступна
docker compose exec db psql -U store_user -d storedb -c "SELECT 1"
```

### Если изменения в коде не применяются

```bash
# 1. Проверь, применился ли reload
docker compose logs -f admin | grep -i reload

# 2. Если нет — перезагрузи контейнер явно
docker compose restart admin

# 3. Если всё ещё не работает — сними старый образ и пересобери
docker compose up --build admin
```

### Если БД "поломана" или миграции не применились

```bash
# 1. Проверь текущее состояние миграций
docker compose exec admin alembic current

# 2. Откати на конкретную версию (если нужно)
docker compose exec admin alembic downgrade -1

# 3. Примени всё заново
docker compose exec admin alembic upgrade head

# 4. Если совсем всё поломалось — очисти БД
docker compose down -v
docker compose up
```

### Интерактивный Python shell в контейнере

```bash
# Запусти Python в контейнере с доступом к БД и моделям
docker compose exec admin python

# Или с поддержкой IPython (если установлен)
docker compose exec admin ipython
```

---

## 📁 Структура файлов разработки

```
sa_fastapi/
├── docker-compose.yml          ← Production-конфиг (НЕ ТРОГАТЬ)
├── docker-compose.override.yml  ← Local dev-конфиг (THIS MAGIC)
├── Dockerfile                   ← Production образ (НЕ ТРОГАТЬ)
├── .env                         ← Production переменные
├── .env.dev                     ← Dev переменные (для локальной разработки)
├── entrypoint.sh               ← Инициализация контейнера
├── src/                         ← Python код (с live-reload)
│   ├── main.py
│   ├── pages/
│   ├── models/
│   ├── services/
│   └── ...
├── alembic/                     ← Миграции БД
│   └── versions/
├── media/                       ← Медиа файлы (bind mount)
└── requirements.txt             ← Python зависимости
```

---

## ⚠️ ВАЖНЫЕ ПРАВИЛА

### ✅ Разрешено делать локально

- ✅ Менять код в `src/` → автоматический reload
- ✅ Создавать/тестировать миграции
- ✅ Запускать тесты в контейнере
- ✅ Изменять `.env` → перезагрузить контейнеры

### ❌ НЕ ДЕЛАЙ

- ❌ `docker compose down -v` перед деплоем на сервер (потеряются важные данные)
- ❌ Не коммитишь `.env` с локальными значениями
- ❌ Не коммитишь `.env.dev` если в нём есть реальные секреты
- ❌ Не трогаешь `docker-compose.yml` (за исключением очень редких случаев)
- ❌ Не пушишь `docker-compose.override.yml` на production!

---

## 🚀 Деплой на Production

**Важно:** Когда ты готов деплоить на VDS:

1. **Ничего не меняется в `docker-compose.yml`** — он уже настроен правильно
2. **На VDS НЕ использует `docker-compose.override.yml`** — его игнорируй
3. **На VDS БД уже инициализирована** — миграции применяются в `entrypoint.sh`
4. **На VDS используется `gunicorn`** — он более стабилен чем `uvicorn`

### Команда деплоя на VDS (примерно)

```bash
# На сервере:
cd /path/to/app
git pull origin main
docker compose pull
docker compose up -d

# Docker Compose автоматически:
# - Пересоберёт образ (если был Dockerfile изменён)
# - Применит миграции (через entrypoint.sh)
# - Запустит gunicorn с 4/2 workers
# - Настроит nginx
```

---

## 📚 Дополнительные команды

### Выполнить команду в контейнере

```bash
# Python скрипт
docker compose exec admin python /app/create_user.py

# Миграции
docker compose exec admin alembic revision --autogenerate -m "message"
docker compose exec admin alembic upgrade head
docker compose exec admin alembic downgrade -1

# Очистить кэш
docker compose exec admin python -c "import shutil; shutil.rmtree('/app/__pycache__', ignore_errors=True)"
```

### Перестроить образ (если менял Dockerfile или requirements.txt)

```bash
# Пересобери и перезапусти
docker compose up --build -d

# Или только конкретный сервис
docker compose up --build admin
```

### Посмотреть все образы и контейнеры

```bash
docker images
docker ps -a
```

---

## 💡 Советы

- **Используй `docker compose logs -f`** для отладки в реальном времени
- **Убедись что порты 8000 и 8001 свободны** перед запуском
- **Если контейнер зависает**, нажми Ctrl+C в терминале (graceful shutdown)
- **Для быстрого рестарта одного сервиса:** `docker compose restart admin`
- **Если всё совсем поломалось:** `docker compose down -v && docker compose up` (⚠️ потеряешь данные БД)

---

## ❓ FAQ

**Q: Почему медленно стартует контейнер?**
A: Uvicorn с `--reload` медленнее чем обычный запуск. Это нормально для dev. На production используется быстрый gunicorn.

**Q: Почему нельзя просто менять docker-compose.yml?**
A: Потому что он используется на VDS/production. Если ты его изменишь локально и случайно припушишь — сломаешь деплой на сервере.

**Q: Как отключить Redis если я не использую кэширование?**
A: В `docker-compose.override.yml` добавь `profiles: ["optional"]` к redis.

**Q: Можно ли запустить тесты?**
A: Да! `docker compose exec admin pytest` (если pytest установлен в requirements.txt)

---

Хорошей разработки! 🎉
