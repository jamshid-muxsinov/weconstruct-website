# WeConstruct CRM & Website

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-green?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge)

Это бэкенд-приложение для компании **WeConstruct**, которое обслуживает как публичный веб-сайт, так и внутреннюю CRM-систему для управления заявками и продажами. Проект построен на FastAPI, SQLAlchemy и полностью готов к запуску в Docker-контейнерах.

## ✨ Ключевые возможности

### 🌐 Публичный сайт
- **Многоязычность:** Полная поддержка русского (`/ru`) и узбекского (`/uz`) языков.
- **Каталог продукции:** Динамическое отображение категорий и товаров из базы данных.
- **Интерактивность:** Формы обратной связи и детали товаров загружаются в модальных окнах без перезагрузки страницы благодаря **HTMX**.
- **Адаптивный дизайн:** Корректное отображение на десктопах, планшетах и мобильных устройствах.

### 💼 CRM-система
- **Канбан-доска:** Интерактивная доска для визуального управления воронкой продаж с drag-and-drop функционалом.
- **360° Обзор клиента:** Единая карточка клиента с полной историей его заявок, задач и заметок.
- **Управление задачами:** Создание и отслеживание задач, привязанных к заявкам и клиентам.
- **Система приглашений:** Безопасная регистрация новых сотрудников по уникальным ссылкам.
- **Уведомления:** Встроенная система оповещений о новых заявках для менеджеров.
- **Экспорт данных:** Возможность выгружать заявки в CSV-формате.

## 🛠️ Технологический стек

- **Бэкенд:** FastAPI, Uvicorn
- **База данных:** PostgreSQL
- **ORM:** SQLAlchemy (async)
- **Миграции:** Alembic
- **Кэширование:** Redis
- **Фронтенд:** Jinja2, HTMX, Alpine.js
- **Аутентификация:** JWT (хранится в HttpOnly cookie)
- **Развертывание:** Docker, Docker Compose

## 🚀 Быстрый старт (Локальная разработка)

### Предварительные требования
- [Git](https://git-scm.com/)
- [Docker](https://www.docker.com/products/docker-desktop/) и Docker Compose

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/jamshid-muxsinov/weconstruct-fastapi.git
cd weconstruct-fastapi
```

### 2. Создайте файл `.env`
Создайте в корне проекта файл `.env` и скопируйте в него содержимое ниже, заменив значения при необходимости.

```env
# Настройки проекта
PROJECT_NAME="WeConstruct CRM"
DEBUG=true
SECRET_KEY=your-super-secret-key-that-is-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200 # 30 дней

# Настройки базы данных PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/mydatabase

# Настройки Redis
REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true
REDIS_TTL=300

# Создание первого администратора при запуске
FIRST_SUPERUSER=admin
FIRST_SUPERUSER_PASSWORD=admin123

# Настройки CORS (можно оставить пустыми для начала)
CORS_ORIGINS=[]
LOG_LEVEL=INFO```
**Важно:** Значения `user`, `password` и `mydatabase` в `DATABASE_URL` должны совпадать со значениями `POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB` в вашем `docker-compose.yml`.

### 3. Сборка и запуск контейнеров
Эта команда установит все зависимости, создаст базу данных и запустит приложение.

```bash
docker-compose up -d --build
```

### 4. Примените миграции базы данных
При первом запуске (и при последующих изменениях моделей) необходимо применить миграции для создания таблиц в БД.

```bash
docker-compose exec web alembic upgrade head
```

## 💻 Использование

- **Публичный сайт** будет доступен по адресу: [http://localhost:8000/ru](http://localhost:8000/ru)
- **CRM-панель** доступна по адресу: [http://localhost:8000/admin](http://localhost:8000/admin)
- **Данные для входа в CRM:** Используйте `FIRST_SUPERUSER` и `FIRST_SUPERUSER_PASSWORD` из вашего `.env` файла.

## ⚙️ Полезные команды

Все команды выполняются из корневой папки проекта.

- **Посмотреть логи приложения:**
  ```bash
  docker-compose logs -f web
  ```
- **Создать нового суперпользователя вручную:**
  ```bash
  docker-compose exec web python create_user.py
  ```
- **Сбросить пароль существующего пользователя:**
  ```bash
  docker-compose exec web python reset_password.py <имя_пользователя>
  ```
- **Остановить все сервисы:**
  ```bash
  docker-compose down
  ```

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. Подробности смотрите в файле `LICENSE`.
