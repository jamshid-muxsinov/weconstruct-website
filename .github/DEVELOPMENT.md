# 🛠️ Локальная разработка (Development Setup)

## ⚡ Быстрый старт (30 секунд)

```bash
# 1️⃣ Первый запуск (с пересборкой)
make dev-up

# 2️⃣ Или используя docker compose напрямую
docker compose -f docker-compose.dev.yml up --build

# 3️⃣ Доступ к приложениям
# Site:  http://localhost:8001
# Admin: http://localhost:8000
```

---

## 📋 Что изменилось для DEV

### ✅ Новые файлы

| Файл | Назначение |
|------|-----------|
| `docker-compose.dev.yml` | Конфигурация для локальной разработки |
| `Dockerfile.dev` | Оптимизированный образ для dev (без npm build) |
| `.env.dev` | Переменные окружения для локального запуска |
| `Makefile` | Удобные команды для dev |
| `.github/DEVELOPMENT.md` | Эта документация |

### ❌ Production остался 100% нетронут

```
docker-compose.yml  ← НЕ МЕНЯЛСЯ (production)
Dockerfile          ← НЕ МЕНЯЛСЯ (production)
```

### 🔄 Главные отличия DEV vs PROD

| Аспект | Production | Development |
|--------|-----------|-------------|
| **Сервер** | Gunicorn (4 workers) | Uvicorn с `--reload` |
| **Фронтенд** | Собирается в Dockerfile | Используется существующий `/src/static/dist` |
| **Код** | Копируется в образ | Bind mount для live-reload |
| **Healthchecks** | Включены | Отключены (ускоряет старт) |
| **Nginx** | Включен (reverse proxy) | Отключен (обращаетесь напрямую) |
| **DEBUG** | false | true |

---

## 🎯 Основные команды

### Запуск/остановка

```bash
# Запустить с пересборкой образов
make dev-up
docker compose -f docker-compose.dev.yml up --build

# Запустить быстро (без пересборки)
make dev-up-fast
docker compose -f docker-compose.dev.yml up

# Остановить
make dev-down
docker compose -f docker-compose.dev.yml down
```

### Логирование

```bash
# Все логи (live)
make dev-logs
docker compose -f docker-compose.dev.yml logs -f

# Только site приложение
make dev-logs-site
docker compose -f docker-compose.dev.yml logs -f site

# Только admin приложение
make dev-logs-admin
docker compose -f docker-compose.dev.yml logs -f admin
```

### БД и миграции

```bash
# Запустить Alembic миграции
make db-migrate

# Полный reset БД (ВСЕ ДАННЫЕ УДАЛЯТСЯ!)
make db-reset

# Подключиться к БД напрямую
docker compose -f docker-compose.dev.yml exec db psql -U dev_user -d weconstruct_dev
```

---

## 🔥 Live-reload (горячая перезагрузка)

Когда вы работаете локально:

1. **Изменили код** в `src/` → Uvicorn автоматически перезагружает приложение ✨
2. **Изменили шаблоны Jinja** → Перезагрузка в браузере
3. **Добавили новую миграцию** → Положите в `alembic/versions/` и перезапустите

```bash
# Код изменится сразу же
# Просто сохраните файл (Ctrl+S) и обновите браузер
```

### Что работает с live-reload

✅ Python код (`src/**/*.py`)  
✅ Jinja шаблоны (`src/templates/**/*.html`)  
✅ CSS/JS (если используете bundler со своим watch режимом)  
✅ Конфиги (некоторые требуют полной перезагрузки)

### Что НЕ работает с live-reload (требует `make dev-up --build`)

❌ Изменения в `requirements.txt` → Пересоберите образ  
❌ Новые переменные в `.env.dev` → Перезапустите контейнер  
❌ Изменения в `Dockerfile.dev` → Пересоберите образ

---

## 🗄️ База данных

### Переменные БД (в `.env.dev`)

```bash
POSTGRES_USER=dev_user
POSTGRES_PASSWORD=dev_password_local
POSTGRES_DB=weconstruct_dev
DATABASE_URL=postgresql+asyncpg://dev_user:dev_password_local@db:5432/weconstruct_dev
```

### Подключение к БД

```bash
# Через docker compose (интерактивный psql)
docker compose -f docker-compose.dev.yml exec db psql -U dev_user -d weconstruct_dev

# Или используйте любой SQL-клиент:
# Host: localhost
# Port: 5432 (проверьте docker-compose.dev.yml)
# User: dev_user
# Password: dev_password_local
# Database: weconstruct_dev
```

### Миграции Alembic

```bash
# Проверить статус миграций
docker compose -f docker-compose.dev.yml exec admin alembic current
docker compose -f docker-compose.dev.yml exec admin alembic history

# Применить все миграции до последней версии
make db-migrate

# Откатить последнюю миграцию
docker compose -f docker-compose.dev.yml exec admin alembic downgrade -1

# Создать новую миграцию (если изменили модели)
docker compose -f docker-compose.dev.yml exec admin alembic revision --autogenerate -m "Your migration message"
```

---

## 🌐 Доступ к приложениям

| Приложение | URL | Назначение |
|------------|-----|-----------|
| **Site** | http://localhost:8001 | Основной сайт (шоп) |
| **Admin** | http://localhost:8000 | CRM админка |
| **Postgres** | localhost:5432 | БД (если пробросили порт) |
| **Redis** | localhost:6379 | Cache (если пробросили порт) |

### Доступ к admin приложению

```bash
# Логин: admin@local.dev
# Пароль: admin123456
# (из .env.dev - FIRST_SUPERUSER и FIRST_SUPERUSER_PASSWORD)
```

---

## 🐛 Отладка (Debugging)

### Логирование

Уровень логирования установлен на `DEBUG` в `.env.dev`:

```bash
LOG_LEVEL=DEBUG
```

Посмотрите логи приложения:

```bash
make dev-logs
```

### Python debugger (pdb)

Добавьте точку останова в код:

```python
import pdb; pdb.set_trace()  # breakpoint в Python 3.7+
# или
breakpoint()
```

Затем запустите:

```bash
docker compose -f docker-compose.dev.yml exec site python -m pdb your_script.py
```

### Проверить здоровье приложений

```bash
# Site healthcheck
curl http://localhost:8001/uz

# Admin healthcheck
curl http://localhost:8000/login
```

---

## 📦 Зависимости

### Добавить новый пакет

```bash
# 1. Добавьте в requirements.txt
echo "new-package-name==1.0.0" >> requirements.txt

# 2. Пересоберите образы
make dev-build

# 3. Перезапустите сервисы
make dev-up-fast
```

### Обновить существующие пакеты

```bash
# Внутри контейнера
docker compose -f docker-compose.dev.yml exec site pip install --upgrade package-name

# Или модифицируйте requirements.txt и пересоберите
```

---

## 🔌 Переменные окружения

Основной файл: `.env.dev`

```bash
# Редактируйте для локальной разработки
nano .env.dev

# После изменения перезапустите сервис
make dev-down
make dev-up
```

### Основные переменные

| Переменная | Default | Описание |
|------------|---------|---------|
| `DEBUG` | `True` | Режим отладки (False в prod) |
| `LOG_LEVEL` | `DEBUG` | Уровень логирования |
| `POSTGRES_PASSWORD` | `dev_password_local` | ⚠️ Временный пароль! |
| `SECRET_KEY` | `dev_secret_key...` | ⚠️ Генерируйте новый в prod |
| `FIRST_SUPERUSER` | `admin@local.dev` | Первый администратор |

### Скрытые переменные (в git .gitignore)

```bash
# Реальный .env для продакшена НЕ коммитится
# Используется только .env.dev для примера
```

---

## 🧹 Очистка и reset

### Полный reset окружения

```bash
# Удалить все контейнеры, volumes и образы
make clean

# Или вручную
docker compose -f docker-compose.dev.yml down -v --rmi local
```

### Очистить только данные БД (сохранить образы)

```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up
```

### Пересоздать только БД

```bash
docker volume rm sa_fastapi_db_data
docker compose -f docker-compose.dev.yml up -d db
```

---

## ⚠️ Частые проблемы

### "Port 8000/8001 already in use"

```bash
# Найти процесс
lsof -i :8000
lsof -i :8001

# Или просто используйте другой порт в docker-compose.dev.yml
# Измените ports: в файле
```

### "Database connection refused"

```bash
# 1. Проверьте, что db сервис запущен
docker compose -f docker-compose.dev.yml ps

# 2. Дождитесь инициализации БД
docker compose -f docker-compose.dev.yml logs db

# 3. Проверьте DATABASE_URL в .env.dev
```

### "Module not found" / Import errors

```bash
# Переустановите зависимости
make dev-build
make dev-up

# Или внутри контейнера
docker compose -f docker-compose.dev.yml exec site pip install -r requirements.txt
```

### Код не перезагружается (live-reload не работает)

```bash
# 1. Проверьте логи
make dev-logs

# 2. Убедитесь, что файл находится в ./src/
# (другие пути не мониторятся)

# 3. Полезный рестарт
docker compose -f docker-compose.dev.yml restart site admin

# 4. Дальше:
make dev-down
make dev-up
```

---

## 📚 Дополнительно

### Документация

- [FastAPI docs](https://fastapi.tiangolo.com)
- [Docker Compose docs](https://docs.docker.com/compose/)
- [SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic migrations](https://alembic.sqlalchemy.org/)

### Структура проекта

```
.
├── src/
│   ├── main.py              # FastAPI приложение
│   ├── core/                # Конфиг, БД, security
│   ├── models/              # SQLAlchemy модели
│   ├── schemas/             # Pydantic схемы
│   ├── services/            # Бизнес логика
│   ├── pages/               # Роутеры и views
│   ├── templates/           # Jinja шаблоны
│   └── static/              # CSS, JS, фавиконы
├── alembic/                 # Миграции БД
├── docker-compose.yml       # Production конфиг
├── docker-compose.dev.yml   # DEV конфиг (новый)
├── Dockerfile               # Production образ
├── Dockerfile.dev           # DEV образ (новый)
├── .env.dev                 # DEV переменные окружения
├── Makefile                 # Удобные команды
└── requirements.txt         # Python зависимости
```

---

## ✨ Tips & Tricks

### Быстрое переключение между dev и prod

```bash
# Работаете локально?
make dev-up

# Готовы к продакшену?
make prod-up
```

### Посмотреть что работает

```bash
# Все сервисы
docker compose -f docker-compose.dev.yml ps

# На продакшене
docker compose ps
```

### Командная работа

Если работаете в команде:

```bash
# Синхронизируйте .env.dev через безопасный канал
# (никогда не коммитьте реальные пароли!)

# Остальные разработчики:
git pull
make dev-up
```

---

## 🚀 Готово к запуску!

```bash
make dev-up
# Ждите пока всё инициализируется...
# Откройте http://localhost:8000 или http://localhost:8001
# Начинайте разработку! 🎉
```

**Вопросы?** Посмотрите логи:
```bash
make dev-logs
```
