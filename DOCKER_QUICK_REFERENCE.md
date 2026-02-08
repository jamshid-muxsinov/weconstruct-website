# ⚡ DOCKER QUICK REFERENCE

## 🚀 Начать разработку (один раз)

```bash
# Перейди в папку проекта
cd /home/tasheet/development/sa_fastapi

# Запусти Docker Compose (БД инициализируется, миграции применятся)
docker compose up -d

# Проверь что все запустилось
docker compose ps

# Смотри логи стартапа
docker compose logs -f admin
```

## ✨ Разработка (каждый день)

```bash
# Запусти проект
docker compose up

# Открой браузер
# Admin: http://localhost:8000
# Site: http://localhost:8001

# Сохраняй файлы — Uvicorn автоматически перезагружается!

# Смотри логи (в другом терминале)
docker compose logs -f admin
```

## 🛑 Остановить проект

```bash
# Только остановить (данные БД сохранятся)
docker compose down

# Полная очистка (потеряются ВСЕ данные)
docker compose down -v
```

## 🐛 Быстрая диагностика

| Проблема | Команда | Решение |
|----------|---------|---------|
| Контейнер не стартует | `docker compose logs admin` | Посмотри ошибку в логах |
| БД недоступна | `docker compose exec db psql -U store_user -d storedb -c "SELECT 1"` | Проверь что db запущена |
| Код не обновляется | `docker compose logs -f admin \| grep reload` | Убедись что видно "Reloading" |
| Тихая ошибка | Ctrl+C, потом `docker compose logs admin` | Посмотри логи полностью |
| Всё ломается | `docker compose down -v && docker compose up` | Полный рестарт |

## 📝 Частые операции

### Просмотр логов

```bash
# Все логи в реальном времени
docker compose logs -f

# Только admin
docker compose logs -f admin

# Только последние 50 строк
docker compose logs --tail=50

# С временными метками
docker compose logs -f -t
```

### Выполнить команду в контейнере

```bash
# Python скрипт
docker compose exec admin python /app/create_user.py

# Python shell
docker compose exec admin python

# Bash shell
docker compose exec admin bash

# Запустить миграцию
docker compose exec admin alembic revision --autogenerate -m "add field"
docker compose exec admin alembic upgrade head
```

### Перезагрузить контейнеры

```bash
# Перезагрузить конкретный сервис
docker compose restart admin

# Остановить и запустить
docker compose stop admin
docker compose start admin

# Полный рестарт всего
docker compose restart
```

### Пересобрать образ

```bash
# Пересобрать (когда менял requirements.txt или Dockerfile)
docker compose up --build admin

# Пересобрать всё
docker compose up --build

# Пересобрать и очистить кэш
docker compose build --no-cache admin
```

## 🔍 Посмотреть конфиг

```bash
# Merged конфиг (что выполняется):
docker compose config

# Только базовый (без override):
docker compose config --no-include-override

# Конфиг конкретного сервиса:
docker compose config | grep -A 20 "service: admin"

# Какие конфиги используются:
docker compose config | head -20
```

## 📊 Информация о контейнерах

```bash
# Все контейнеры
docker compose ps

# С подробностями
docker compose ps --all

# Только работающие
docker compose ps

# Образы проекта
docker images | grep sa_fastapi
```

## 💾 Работа с БД

```bash
# Подключиться к БД
docker compose exec db psql -U store_user -d storedb

# Посмотреть таблицы
docker compose exec db psql -U store_user -d storedb -c "\dt"

# Запустить SQL скрипт
docker compose exec db psql -U store_user -d storedb -f /app/script.sql

# Бэкап БД
docker compose exec db pg_dump -U store_user storedb > backup.sql

# Восстановить БД
docker compose exec -T db psql -U store_user storedb < backup.sql
```

## 🔧 Миграции Alembic

```bash
# Посмотреть текущую версию БД
docker compose exec admin alembic current

# История всех миграций
docker compose exec admin alembic history

# Создать новую миграцию (автогенерация)
docker compose exec admin alembic revision --autogenerate -m "add user fields"

# Применить все миграции
docker compose exec admin alembic upgrade head

# Откатить на одну версию назад
docker compose exec admin alembic downgrade -1

# Откатить на конкретную версию
docker compose exec admin alembic downgrade <revision>
```

## 🔐 Пользователи

```bash
# Создать нового пользователя (если есть скрипт)
docker compose exec admin python /app/create_user.py

# Сбросить пароль (если есть скрипт)
docker compose exec admin python /app/reset_password.py

# Создать суперпользователя вручную (Python shell)
docker compose exec admin python
```

## 📦 Зависимости

```bash
# Установить новый пакет
docker compose exec admin pip install requests

# Обновить requirements.txt
docker compose exec admin pip freeze > requirements.txt

# Проверить какие пакеты установлены
docker compose exec admin pip list

# Пересобрать с новыми зависимостями
docker compose up --build admin
```

## 🌐 Сеть и порты

```bash
# Какие порты открыты
docker compose ps

# Проверить доступность сервиса
docker compose exec admin curl http://site:8000/uz

# Проверить доступность БД из app
docker compose exec admin python -c "import asyncio; from src.core.db import check_db_connection; asyncio.run(check_db_connection())"

# Посмотреть IP адреса контейнеров
docker compose exec admin ip addr

# Проверить DNS
docker compose exec admin nslookup db
```

## 🔗 Полезные URL'ы

| Что | URL | Логин/Пароль |
|-----|-----|---|
| Admin Panel | http://localhost:8000 | admin / admin123 |
| Shop (Site) | http://localhost:8001/uz | - |
| PostgreSQL | localhost:5432 | store_user / sqwcstore4825 |
| Redis | localhost:6379 | - |
| Nginx | http://localhost | - |

## 🚨 Emergency Commands

```bash
# Полная перезагрузка (потеря данных)
docker compose down -v && docker compose up

# Убить зависший контейнер
docker compose kill admin

# Посмотреть что ест ресурсы
docker compose stats

# Очистить всё неиспользуемое
docker system prune -a

# Посмотреть ошибки docker daemon
docker compose logs

# Проверить версию docker
docker --version
docker compose version
```

## ✅ Checklist перед коммитом

```bash
# Убедись что изменения не трогают production файлы:
[ ] git diff docker-compose.yml (должна быть пусто!)
[ ] git diff Dockerfile (должна быть пусто!)
[ ] git diff entrypoint.sh (должна быть пусто!)
[ ] git diff .env (должна быть пусто!)

# Убедись что добавил dev файлы в .gitignore:
[ ] docker-compose.override.yml в .gitignore
[ ] .env.dev может быть в .gitignore (если есть секреты)

# Добавляй только dev файлы:
git add DEVELOPMENT.md
git add DOCKER_ANALYSIS.md
git add .env.dev
git commit -m "Add local development setup with docker-compose.override.yml"
```

## 📚 Дополнительно

```bash
# Посмотреть все доступные команды
docker compose --help

# Посмотреть помощь для конкретной команды
docker compose up --help

# Docker документация
docker --help
```

---

**Памятка:**
- 🟢 **Green** — контейнер запущен
- 🔴 **Red** — контейнер упал
- ⚪ **Gray** — контейнер не запущен

```bash
# Проверь статус
docker compose ps

# Всё должно быть зеленое!
```
