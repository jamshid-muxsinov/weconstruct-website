# 🚀 LOCAL DEVELOPMENT SETUP

> **Быстрый старт для локальной разработки с Docker**

## ⚡ В одну команду

```bash
docker compose up
```

Всё! Открой http://localhost:8000 (Admin) или http://localhost:8001 (Site).

---

## 📖 Документация

| Документ | Для кого | Что читать |
|----------|----------|-----------|
| **FINAL_REPORT.md** | Все | 📋 Обзор что было сделано, чек-лист |
| **DEVELOPMENT.md** | Разработчики | 🚀 Как запустить, как менять код, FAQ |
| **DOCKER_ANALYSIS.md** | DevOps/Архитекторы | 🐳 Полный анализ Docker архитектуры |
| **DOCKER_QUICK_REFERENCE.md** | Все | ⚡ Шпаргалка с командами |

---

## ✅ Проверка что всё установлено

```bash
bash verify_setup.sh
```

---

## 🎯 Основные команды

```bash
# Запустить (БД и миграции инициализируются автоматически)
docker compose up

# Остановить (данные БД сохранятся)
docker compose down

# Полная очистка (потеряются данные БД!)
docker compose down -v

# Посмотреть логи
docker compose logs -f admin

# Перезагрузить сервис
docker compose restart admin
```

---

## 🔗 Доступ к приложению

| Сервис | URL | Логин/Пароль |
|--------|-----|---|
| **Admin Panel** | http://localhost:8000 | admin / admin123 |
| **Shop (Site)** | http://localhost:8001/uz | - |
| **PostgreSQL** | localhost:5432 | store_user / sqwcstore4825 |
| **Redis** | localhost:6379 | - |

---

## 💡 Как разрабатывать

```bash
# 1. Отредактируй файл
vim src/pages/shop_pages.py

# 2. Сохрани (Ctrl+S)

# 3. Uvicorn автоматически перезагружается (200ms)
docker compose logs -f admin
# Увидишь: "Reloading..."

# 4. Refresh браузер (F5) → видны изменения
```

**Никаких `docker compose build` или перезагрузок контейнеров!** 🎉

---

## 📋 Что было сделано

✅ **docker-compose.override.yml** — главный файл для dev (uvicorn + bind mounts)  
✅ **.env.dev** — пример переменных для dev  
✅ **Production не трогается** — docker-compose.yml, Dockerfile, entrypoint.sh без изменений  
✅ **Zero-touch solution** — все dev файлы добавлены, production immutable  
✅ **Документация** — 4 полных гайда  

---

## ⚠️ Критические правила

❌ **НЕ ТРОГАЙ:** docker-compose.yml, Dockerfile, entrypoint.sh, .env  
❌ **НЕ ПУШЬ:** docker-compose.override.yml и .env.dev на сервер  
✅ **ИСПОЛЬЗУЙ:** docker-compose.override.yml локально для dev  
✅ **КОММИТИШЬ:** DEVELOPMENT.md, DOCKER_ANALYSIS.md, verify_setup.sh  

---

## 🚨 Если что-то сломалось

```bash
# Посмотри логи
docker compose logs admin

# Перезагрузи контейнер
docker compose restart admin

# Или полный рестарт (потеряются данные)
docker compose down -v && docker compose up
```

**Для деталей:** см. DEVELOPMENT.md → "🐛 Отладка"

---

## 📚 Дальнейшее

1. **Запусти:** `docker compose up`
2. **Открой:** http://localhost:8000
3. **Читай:** DEVELOPMENT.md для подробной инструкции
4. **Кодь:** Измени файл в src/ → автоматический reload → готово!

---

**Questions?** Прочитай документацию:
- 🚀 Быстрый старт → DEVELOPMENT.md
- 🐳 Как это работает → DOCKER_ANALYSIS.md
- ⚡ Частые команды → DOCKER_QUICK_REFERENCE.md

Good luck! 🎉
