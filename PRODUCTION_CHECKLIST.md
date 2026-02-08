# ✅ PRODUCTION DEPLOYMENT CHECKLIST

> Обязательная проверка перед деплоем на VDS

## ⚠️ КРИТИЧЕСКИЕ ПРОВЕРКИ

### 1. Git - Production конфиги не изменены

```bash
# ❌ STOP if these are changed!
git diff docker-compose.yml
git diff Dockerfile
git diff entrypoint.sh
git diff .env
git diff alembic.ini

# ✅ Должны быть пусто для всех 5 файлов!
```

**Если есть изменения:**
```bash
# Откатить
git checkout docker-compose.yml
git checkout Dockerfile
git checkout entrypoint.sh
git checkout .env
git checkout alembic.ini

# Или
git reset --hard HEAD
```

### 2. Git - Dev файлы в .gitignore

```bash
# Проверь что эти файлы В .gitignore
grep "docker-compose.override.yml" .gitignore
grep "docker-compose.dev.yml" .gitignore
grep ".env.local" .gitignore

# ✅ Все три должны быть в .gitignore
```

### 3. Git - Не коммитишь dev файлы

```bash
# Проверь что НЕ было добавлено в коммит
git log --oneline -20 | grep -i "override\|dev.yml\|\.env\.dev"

# ❌ STOP if found!
# Откатить последний коммит
git reset --soft HEAD~1
git reset HEAD docker-compose.override.yml .env.dev
git commit --amend
```

### 4. Docker Image - Проверь что собрался

```bash
# На локальной машине (перед push)
docker compose build --no-cache site admin

# ✅ Build должен пройти без ошибок
```

### 5. Docker Image - Проверь что есть gunicorn

```bash
# Проверь что production образ использует gunicorn, а не uvicorn
docker compose config --no-include-override | grep -A5 "command:"

# ✅ Должен содержать: "gunicorn -w 4" и "gunicorn -w 2"
# ❌ НЕ должен содержать: "uvicorn"
```

---

## ✅ ЛОКАЛЬНЫЕ ПРОВЕРКИ (перед push)

### 1. Проверь что локально всё работает

```bash
# Локально на машине (с docker-compose.override.yml)
docker compose up

# Ждем инициализации БД (~30 сек)
docker compose logs admin | grep -i "migrations applied"

# Проверь админ-панель
curl http://localhost:8000/login -I
# ✅ HTTP 200 или 302 (редирект)

# Проверь сайт
curl http://localhost:8001/uz -I
# ✅ HTTP 200 или 302
```

### 2. Проверь что код менялся с reload

```bash
# В разработке (если меняли код)
vim src/pages/shop_pages.py

# Сохрани файл
# Смотри логи
docker compose logs -f admin | grep -i "reload"
# ✅ Должно быть: "Reloading"

# Это не повлияет на production, но убедись что всё работает локально
```

### 3. Очисть локальные файлы перед push

```bash
# Убедись что не оставил временные файлы
git status

# ❌ Не должно быть:
# - .env.local
# - docker-compose.dev.yml
# - .vscode/settings.json (если редактировал)
# - __pycache__ (должны быть в .gitignore)
# - *.pyc, *.pyo

# Удали если есть
rm -f .env.local docker-compose.dev.yml
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
```

---

## 🚀 ПЕРЕД ДЕПЛОЕМ НА VDS

### 1. Финальная проверка на локальной машине

```bash
# Убедись что override применяется ТОЛЬКО локально
ls -la docker-compose.override.yml
# ✅ Файл существует на локальной машине

# Но НЕ на сервере (будет проверено при pull)
```

### 2. Push на Git

```bash
# Коммит с документацией и новыми dev файлами
git add DEVELOPMENT.md DOCKER_ANALYSIS.md DOCKER_QUICK_REFERENCE.md SETUP_SUMMARY.md LOCAL_SETUP.md verify_setup.sh .gitignore

git commit -m "Add local development setup with docker-compose.override.yml

- Add docker-compose.override.yml for local development (uvicorn + live-reload)
- Add .env.dev as example for development environment
- Add comprehensive documentation (DEVELOPMENT.md, DOCKER_ANALYSIS.md, etc)
- Add verify_setup.sh for setup verification
- Update .gitignore to exclude development files
- Production config remains unchanged (zero-touch)"

git push origin main
```

### 3. На VDS - Обычный деплой (без изменений)

```bash
# На сервере (как всегда)
cd /path/to/sa_fastapi

# Pull с новыми dev файлами (они не повлияют на production)
git pull origin main

# Если менялся Dockerfile или requirements.txt
docker compose build

# Запуск (используется ТОЛЬКО docker-compose.yml, override НЕ существует)
docker compose up -d

# ✅ Production работает как раньше
# ✅ Development файлы на сервере есть (но не используются)
```

---

## 🔍 ПРОВЕРКА НА VDS ПОСЛЕ ДЕПЛОЯ

### 1. Убедись что production использует gunicorn

```bash
# На VDS
docker compose ps

# Проверь команды
docker compose logs admin | grep -i "command"
docker compose logs site | grep -i "command"

# ✅ Должны содержать: "gunicorn"
# ❌ НЕ должны содержать: "uvicorn"
```

### 2. Убедись что override НЕ применился

```bash
# На VDS
ls -la docker-compose.override.yml
# ❌ Файл НЕ должен существовать (или должен быть .gitignore'd)

# ИЛИ проверь что конфиг production
docker compose config --no-include-override | grep -i "gunicorn"
# ✅ Должен содержать gunicorn
```

### 3. Проверь что приложение доступно

```bash
# На VDS
curl http://localhost:8000/login -I
curl http://localhost:8001/uz -I

# ✅ Должны быть HTTP 200 или редирект (302)
```

### 4. Проверь логи

```bash
# На VDS - нет ошибок при стартапе
docker compose logs admin | head -50
docker compose logs site | head -50

# ✅ Не должно быть критических ошибок
# ℹ️ Может быть warning'и - это OK
```

---

## 📋 ИТОГОВЫЙ ЧЕК-ЛИСТ

```
ЛОКАЛЬНО (перед push):
[ ] git diff docker-compose.yml — пусто ✅
[ ] git diff Dockerfile — пусто ✅
[ ] git diff entrypoint.sh — пусто ✅
[ ] git diff .env — пусто ✅
[ ] docker-compose.override.yml в .gitignore ✅
[ ] docker compose up локально работает ✅
[ ] docker compose logs -f показывает uvicorn ✅ (locально)
[ ] Нет временных файлов (git status clean) ✅
[ ] Готов к push ✅

НА VDS (после git pull):
[ ] docker compose ps все контейнеры running ✅
[ ] docker compose logs admin содержит gunicorn ✅
[ ] docker compose logs site содержит gunicorn ✅
[ ] docker-compose.override.yml НЕ применяется ✅
[ ] http://localhost:8000/login доступен ✅
[ ] http://localhost:8001/uz доступен ✅
[ ] Нет критических ошибок в логах ✅
[ ] Production работает как раньше ✅
```

---

## 🚨 EMERGENCY - если что-то пошло не так на VDS

### Откат деплоя

```bash
# На VDS
git revert HEAD
git pull
docker compose down
docker compose up -d

# Проверь что всё работает
docker compose logs admin
```

### Откат на предыдущую версию

```bash
# На VDS
git reset --hard HEAD~1
docker compose down
docker compose up -d
```

### Полная переинициализация

```bash
# На VDS (потеря данных!)
docker compose down -v
git pull
docker compose up -d

# Пересоздаст БД с нуля, применит миграции
```

---

## 📞 КОНТАКТЫ ДЛЯ ПОМОЩИ

Если что-то не работает:

1. **Посмотри логи:**
   ```bash
   docker compose logs -f admin
   ```

2. **Проверь конфиг:**
   ```bash
   docker compose config
   ```

3. **Перезагрузи контейнеры:**
   ```bash
   docker compose restart
   ```

4. **Посмотри документацию:**
   - DEVELOPMENT.md → "🐛 Отладка"
   - DOCKER_QUICK_REFERENCE.md → "🚨 Emergency Commands"

---

## ✅ READY FOR PRODUCTION!

Если всё пройдено ✅, можешь быть уверен что:
- ✅ Production не будет сломан
- ✅ Development на локальной машине работает
- ✅ Zero-touch solution для production
- ✅ Документация полная и актуальная

**Good luck! 🚀**
