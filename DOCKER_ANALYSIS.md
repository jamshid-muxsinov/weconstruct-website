# 🐳 АНАЛИЗ DOCKER/DOCKER-COMPOSE АРХИТЕКТУРЫ

## 📋 Содержание
1. [Текущая Production архитектура](#текущая-production-архитектура)
2. [Проблемы для локальной разработки](#проблемы-для-локальной-разработки)
3. [Решение: docker-compose.override.yml](#решение-docker-composeoverrideyml)
4. [Как это работает](#как-это-работает)
5. [Файловая структура](#файловая-структура)

---

## Текущая Production архитектура

### **Dockerfile (Multi-stage build)**

```dockerfile
Stage 1: Node.js Builder
├── node:18-alpine
├── Копирует package*.json
├── npm install
├── npm run build → /app/src/static/dist/
└── Выходит

Stage 2: Python App (финальный образ)
├── python:3.11-slim
├── pip install requirements.txt
├── Копирует src/, alembic/, entrypoint.sh
├── Копирует скомпилированный фронтенд из Stage 1
├── RUN chmod +x entrypoint.sh
└── ENTRYPOINT ["/app/entrypoint.sh"]
```

**Ключевые моменты:**
- ✅ Multi-stage build: фронтенд собирается один раз, потом копируется (оптимизация)
- ✅ Полное разделение frontend и backend сборки
- ✅ Кэширование на каждом слое (requirements.txt отдельно)
- ⚠️ Статика попадает в образ при сборке (для dev это проблема)

### **docker-compose.yml (Production)**

```yaml
Services:
├── db (PostgreSQL 15)
│   ├── Image: postgres:15
│   ├── Volume: db_data (named)
│   ├── Env: PGTZ=Asia/Tashkent
│   └── Health: none (для БД не нужна)
│
├── redis (Redis)
│   ├── Image: redis:7-alpine
│   └── Ports: 6379 (internal)
│
├── site (FastAPI - Shop)
│   ├── Image: sa_fastapi:latest (из Dockerfile)
│   ├── Command: gunicorn -w 4 (4 workers)
│   ├── Env: APP_TO_RUN=site
│   ├── Ports: 8001:8000
│   ├── Volumes: 
│   │   - .:/app (весь проект)
│   │   - ./media:/app/media (медиа отдельно)
│   ├── Depends: db, redis
│   └── Health: curl http://localhost:8000/uz
│
├── admin (FastAPI - CRM)
│   ├── Image: sa_fastapi:latest (тот же образ)
│   ├── Command: gunicorn -w 2 (2 workers)
│   ├── Env: APP_TO_RUN=admin
│   ├── Ports: 8000:8000
│   ├── Volumes:
│   │   - .:/app
│   │   - ./media:/app/media
│   │   - ./config/credentials.json:/app/credentials.json:ro (read-only)
│   ├── Depends: db, redis
│   └── Health: curl http://localhost:8000/login
│
└── nginx (Nginx)
    ├── Image: nginx:latest
    ├── Ports: 80:80, 443:443
    ├── Volumes:
    │   - ./nginx/nginx.conf (read-only)
    │   - /etc/letsencrypt (SSL сертификаты, read-only)
    │   - ./media (read-only)
    │   - ./src/static (read-only)
    ├── Depends: site, admin (health)
    └── Restart: unless-stopped
```

**Production Flow:**
```
User Request
    ↓
Nginx (80/443) [внешний мир]
    ├→ /uz/* → site:8000 (shop)
    └→ /admin/* → admin:8000 (crm)
    ↓
site/admin (Gunicorn uvicorn workers)
    ├→ Database (PostgreSQL)
    └→ Cache (Redis)
```

### **entrypoint.sh (Инициализация)**

```bash
#!/bin/sh
set -e

# 1. Парсит DATABASE_URL и извлекает хост:порт
# 2. Ждет пока PostgreSQL будет доступен (netcat -z)
# 3. Запускает: alembic upgrade head (миграции)
# 4. Выполняет: exec "$@" (передает управление gunicorn)
```

**Почему это важно:**
- ✅ БД гарантированно готова перед стартом приложения
- ✅ Миграции применяются автоматически при каждом запуске
- ✅ Если миграция упадет — контейнер не стартанет (fail-fast)

### **main.py (Dual-App Application)**

```python
# Переменная окружения APP_TO_RUN определяет какое приложение запустить

if APP_TO_RUN == "site":
    app = create_site_app()  # Публичный сайт (FastAPI)
elif APP_TO_RUN == "admin":
    app = create_admin_app()  # CRM панель (FastAPI)
else:
    app = create_admin_app()  # Default

# Both apps на одном образе → экономия памяти и времени сборки
```

**Преимущества:**
- ✅ Один образ → две разные услуги
- ✅ Легко масштабировать (добавить еще site/admin контейнеров)
- ✅ Разные ENV переменные → разные поведения

### **.env (Production Variables)**

```bash
DATABASE_URL=postgresql+asyncpg://store_user:sqwcstore4825@db:5432/storedb
# ↑ Хост 'db' — это имя сервиса в docker-compose

REDIS_URL=redis://redis:6379/0
# ↑ Хост 'redis' — это имя сервиса в docker-compose

DEBUG=true
CACHE_ENABLED=true
SECRET_KEY=<production-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

**Важно:** Все хостнеймы (`db`, `redis`) — это имена сервисов в docker-compose. Docker автоматически создает DNS записи внутри сети.

---

## Проблемы для локальной разработки

### **Проблема 1: Gunicorn + Multi-worker**

| Параметр | Production | Dev |
|----------|-----------|-----|
| Сервер | Gunicorn + Uvicorn workers | Uvicorn solo |
| Workers | 4 (site), 2 (admin) | 1 (auto-reload) |
| Reload | ❌ Нет | ✅ Нужен |
| Время старта | ~2-3 сек | ~1 сек |
| Время перезагрузки | 30-60 сек | ~200 мс |

**Проблема:** Каждое изменение кода → пересборка образа → 2-3 минуты ждать

**Решение:** Заменить `gunicorn` на `uvicorn --reload` в dev-режиме

### **Проблема 2: Статика в образе**

```
Dockerfile копирует:
  - npm run build → /app/src/static/dist/
  - Фронтенд попадает в слой образа
  
Когда ты меняешь CSS/JS локально:
  - Файл меняется на хосте
  - Но в контейнере старая версия из образа
  - Нужно пересобрать образ → 2-3 минуты
```

**Решение:** Использовать bind mount (`volumes`) вместо копирования

### **Проблема 3: Отсутствие live-reload для Python кода**

```
Production workflow:
  git push → CI/CD → docker compose build → docker compose up -d
  
Dev workflow (без solution):
  vim src/pages/shop.py → docker compose down → docker compose build → docker compose up
  (каждый раз 2-3 минуты)
  
Dev workflow (с solution):
  vim src/pages/shop.py → автоматический reload в контейнере (200 мс)
```

**Решение:** Uvicorn с `--reload` + bind mount для `/app/src`

### **Проблема 4: Health checks медленные**

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/login"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s
```

**Проблема:** В dev, при частых перезагрузках, docker-compose ждет health check. Это замедляет разработку.

**Решение:** В dev отключить `healthcheck: ~` или `healthcheck: disable`

---

## Решение: docker-compose.override.yml

### **Как это работает:**

Docker Compose **автоматически** применяет `docker-compose.override.yml` если файл существует:

```bash
# Эта команда:
docker compose up

# Эквивалентна:
docker compose -f docker-compose.yml -f docker-compose.override.yml up

# Файлы мержатся (merge):
# 1. Базовый конфиг загружается из docker-compose.yml
# 2. Override применяется поверх (переопределяет ключи)
# 3. Результат используется
```

### **Что переопределяет docker-compose.override.yml**

#### **site service (instead of gunicorn):**
```yaml
# production (docker-compose.yml):
command: gunicorn --chdir /app/src -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 main:app

# development (docker-compose.override.yml):
command: >
  uvicorn 
  --host 0.0.0.0 
  --port 8000 
  --reload
  --reload-dirs /app/src
  main:app
```

**Различия:**
- ✅ `-w 4` (4 workers) → `--reload` (1 worker + автоматический рестарт при изменении)
- ✅ `gunicorn` → `uvicorn` (uvicorn more flexible)
- ✅ `--reload-dirs /app/src` (смотри только src/, не весь /app)

#### **Volumes (bind mounts вместо copy):**
```yaml
# production (docker-compose.yml):
volumes:
  - .:/app              # только для данных (old config)
  - ./media:/app/media

# development (docker-compose.override.yml):
volumes:
  - .:/app              # весь проект (live changes)
  - ./src:/app/src      # Python код (с приоритетом)
  - ./media:/app/media  # медиа
  - /app/__pycache__    # исключить кэш из volume
  - /app/src/__pycache__
```

**Важно:** Позже volume в списке имеет приоритет!
```yaml
volumes:
  - .:/app           # Сначала весь проект монтируется
  - ./src:/app/src   # Потом ./src переопределяет /app/src из first mount
  # Результат: /app/src from host, остальное из .:/app
```

#### **Environment переменные:**
```yaml
# production:
environment:
  - APP_TO_RUN=site
  - FORWARDED_ALLOW_IPS=*

# development:
environment:
  - APP_TO_RUN=site
  - DEBUG=true        # ← added for better logging
  - LOG_LEVEL=DEBUG   # ← added
  - PYTHONUNBUFFERED=1  # ← added (live logs)
  - PYTHONDONTWRITEBYTECODE=1  # ← added (no .pyc files)
```

#### **Health checks отключены:**
```yaml
# production:
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/uz"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 30s

# development:
healthcheck: ~  # ← отключить в dev (медленно)
```

#### **Interactive mode для дебага:**
```yaml
# development:
stdin_open: true  # ← оставить stdin открытым
tty: true         # ← включить TTY (для Ctrl+C)
```

---

## Как это работает

### **Сценарий 1: Локальная разработка (с override)**

```bash
$ docker compose up

# Docker Compose:
# 1. Загружает docker-compose.yml
# 2. Обнаруживает docker-compose.override.yml
# 3. Мержит конфиги
# 4. Запускает с merged конфигом

# Результат:
# - site запускается с uvicorn --reload (не gunicorn)
# - admin запускается с uvicorn --reload (не gunicorn)
# - ./src монтируется как bind mount
# - health checks отключены

# Разработчик:
$ vim src/pages/shop.py
$ # Uvicorn автоматически перезагружается
$ # Логи показывают: "Reloading..."
$ # Refresh в браузере → видны изменения
```

### **Сценарий 2: Production на VDS (без override)**

```bash
# На сервере docker-compose.override.yml НЕ существует

$ docker compose up -d

# Docker Compose:
# 1. Загружает docker-compose.yml
# 2. docker-compose.override.yml НЕ НАЙДЕН
# 3. Использует только оригинальный конфиг

# Результат:
# - site запускается с gunicorn -w 4 (как должно быть)
# - admin запускается с gunicorn -w 2 (как должно быть)
# - Полноценное production окружение
# - Health checks включены

# Production остается неизменным ✅
```

---

## Файловая структура

### **Что не трогаем (Production Immutable):**

```
✅ docker-compose.yml
   ├─ site service с gunicorn -w 4
   ├─ admin service с gunicorn -w 2
   ├─ db с postgresql:15
   ├─ redis с redis:7-alpine
   ├─ nginx с production конфигом
   └─ Все volumes, networks, restart policies

✅ Dockerfile
   ├─ Stage 1: Node.js npm build
   └─ Stage 2: Python 3.11 образ

✅ .env (production переменные)
   ├─ DATABASE_URL=db:5432
   ├─ REDIS_URL=redis:6379
   └─ SECRET_KEY=<production-value>

✅ entrypoint.sh
   ├─ Ожидание БД
   ├─ alembic upgrade head
   └─ exec gunicorn
```

### **Что добавляем (Development Only):**

```
➕ docker-compose.override.yml
   ├─ Переопределяет command на uvicorn --reload
   ├─ Добавляет bind mounts для src/
   ├─ Отключает health checks
   └─ Добавляет DEBUG переменные

➕ .env.dev
   ├─ DATABASE_URL=db:5432 (localhost для локального контейнера)
   ├─ REDIS_URL=redis:6379
   ├─ DEBUG=true
   └─ Тестовые credentials

➕ DEVELOPMENT.md (this guide)
   └─ Инструкции для разработчиков

➕ DOCKER_ANALYSIS.md (this file)
   └─ Техническая документация
```

---

## Команды запуска

### **Production (на VDS)**
```bash
# Не меняется!
docker compose up -d

# или с явными флагами:
docker compose -f docker-compose.yml up -d
```

### **Development (локально)**
```bash
# Автоматически применяет override:
docker compose up

# Или явно (если нужно):
docker compose -f docker-compose.yml -f docker-compose.override.yml up

# С пересборкой образа (если менял requirements.txt):
docker compose up --build

# В фоне:
docker compose up -d
```

### **Остановка и очистка**
```bash
# Остановить контейнеры (данные сохранятся):
docker compose down

# Полная очистка (потеряются данные БД):
docker compose down -v
```

---

## Отладка и логирование

### **Посмотреть как применяется override**

```bash
# Docker compose выведет merged конфиг:
docker compose config

# Ищи вот эти отличия:
# command: uvicorn ... (не gunicorn)
# volumes: содержит ./src:/app/src
# healthcheck: null или ~
```

### **Проверить какие переменные используются**

```bash
# Какие файлы используются:
docker compose config | grep "# source:"

# Или посмотреть конкретный сервис:
docker compose config --services
```

### **Live логирование**

```bash
# Все логи в реальном времени:
docker compose logs -f

# Только конкретный сервис:
docker compose logs -f admin

# Последние N строк:
docker compose logs --tail=50 site

# С временными метками:
docker compose logs -f -t admin
```

---

## Технические детали

### **Как Docker Compose мержит конфиги**

1. **Список services мержится** — новые services добавляются, существующие переопределяются
2. **Внутри сервиса** — ключи переопределяются или расширяются:
   - `command` → полностью заменяется
   - `environment` → мержится (новые переменные добавляются)
   - `volumes` → добавляются (не заменяются!)
   - `ports` → добавляются
   - `healthcheck: ~` → удаляет healthcheck из base

### **Порядок volume мономерования**

Если указаны несколько volumes:
```yaml
volumes:
  - .:/app              # Сначала монтируется
  - ./src:/app/src      # Потом перемонтируется более специфичный путь
  - /app/__pycache__    # Исключаются из монтирования (пустой volume)
```

Внутри контейнера:
- `/app/src` → содержимое с хоста `./src`
- `/app/pages` → содержимое с хоста `./pages` (из `.:/app`)
- `/app/__pycache__` → пустой (исключено)

### **Как узнать какой конфиг используется**

```bash
# Посмотреть merged конфиг (что выполняется):
docker compose config | less

# Посмотреть только base конфиг (без override):
docker compose config --no-include-override | less

# Различия:
diff <(docker compose config --no-include-override) <(docker compose config)
```

---

## Критические моменты

### ⚠️ docker-compose.override.yml НЕ пушится на продакшн

```bash
# Убедись что это в .gitignore:
cat .gitignore | grep override

# Если нет, добавь:
echo "docker-compose.override.yml" >> .gitignore
```

### ⚠️ .env.dev НЕ содержит реальных секретов

```bash
# Проверь:
cat .env.dev | grep -i secret
# Не должно быть реальных значений из production!
```

### ⚠️ Production конфиг остается неизменным

```bash
# Ни одна из этих команд:
git diff docker-compose.yml
git diff Dockerfile
git diff entrypoint.sh

# Не должна выдать изменений!
```

---

## Заключение

| Аспект | Production | Development |
|--------|-----------|-------------|
| **Конфиг** | `docker-compose.yml` | `docker-compose.yml` + `docker-compose.override.yml` |
| **Сервер** | Gunicorn (fast, stable) | Uvicorn (fast reload) |
| **Workers** | 4/2 | 1 + auto-reload |
| **Статика** | В образе | Bind mount (live) |
| **Код** | В образе | Bind mount (live) |
| **Логирование** | INFO | DEBUG |
| **Health checks** | Включены | Отключены |
| **Результат** | Stable production | Fast development |

Этот подход позволяет:
- ✅ Разрабатывать локально как в Node.js (hot reload)
- ✅ Не трогать production конфиг
- ✅ Легко скейлить на production
- ✅ Минимизировать риск ошибок при деплое

🎉
