#!/bin/bash
# verify_setup.sh
# Скрипт для проверки что всё правильно установлено для локальной разработки

set -e

echo "🔍 Проверка настройки локальной разработки..."
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1 существует"
        return 0
    else
        echo -e "${RED}❌${NC} $1 не найден!"
        return 1
    fi
}

check_not_modified() {
    local file=$1
    local expected_status=$2
    
    if git diff --quiet "$file" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $file не изменен (как надо)"
        return 0
    else
        echo -e "${RED}❌${NC} $file изменен! Это может сломать production!"
        git diff "$file"
        return 1
    fi
}

echo -e "${BLUE}1️⃣  Проверка что Production конфиги НЕ изменены${NC}"
echo "─────────────────────────────────────────────"
check_not_modified "docker-compose.yml" || exit 1
check_not_modified "Dockerfile" || exit 1
check_not_modified "entrypoint.sh" || exit 1
echo ""

echo -e "${BLUE}2️⃣  Проверка что Development файлы созданы${NC}"
echo "─────────────────────────────────────────────"
check_file "docker-compose.override.yml" || exit 1
check_file ".env.dev" || exit 1
check_file "DEVELOPMENT.md" || exit 1
check_file "DOCKER_ANALYSIS.md" || exit 1
check_file "DOCKER_QUICK_REFERENCE.md" || exit 1
check_file "SETUP_SUMMARY.md" || exit 1
echo ""

echo -e "${BLUE}3️⃣  Проверка .gitignore${NC}"
echo "─────────────────────────────────────────────"
if grep -q "docker-compose.override.yml" .gitignore; then
    echo -e "${GREEN}✅${NC} docker-compose.override.yml в .gitignore (good!)"
else
    echo -e "${YELLOW}⚠️${NC}  docker-compose.override.yml НЕ в .gitignore"
    echo "   Добавь в .gitignore эту строку:"
    echo "   docker-compose.override.yml"
fi

if grep -q "docker-compose.dev.yml" .gitignore; then
    echo -e "${GREEN}✅${NC} docker-compose.dev.yml в .gitignore (good!)"
else
    echo -e "${YELLOW}⚠️${NC}  docker-compose.dev.yml НЕ в .gitignore"
fi
echo ""

echo -e "${BLUE}4️⃣  Проверка Docker Compose конфига${NC}"
echo "─────────────────────────────────────────────"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅${NC} Docker установлен"
    docker --version
else
    echo -e "${RED}❌${NC} Docker не найден! Установи Docker"
    exit 1
fi

if command -v docker compose &> /dev/null; then
    echo -e "${GREEN}✅${NC} Docker Compose установлен"
    docker compose version
else
    echo -e "${RED}❌${NC} Docker Compose не найден!"
    exit 1
fi
echo ""

echo -e "${BLUE}5️⃣  Проверка файлов docker-compose.override.yml${NC}"
echo "─────────────────────────────────────────────"
if docker compose config > /tmp/compose-config.yaml 2>&1; then
    echo -e "${GREEN}✅${NC} docker-compose конфиг валидный"
    
    # Проверь что в конфиге есть переопределения
    if grep -q "uvicorn" /tmp/compose-config.yaml; then
        echo -e "${GREEN}✅${NC} Обнаружен uvicorn (override применен)"
    else
        echo -e "${RED}❌${NC} uvicorn не найден в конфиге (override не применен?)"
    fi
    
    if grep -q "rebuild-dirs" /tmp/compose-config.yaml || grep -q "reload" /tmp/compose-config.yaml; then
        echo -e "${GREEN}✅${NC} Обнаружен reload механизм"
    else
        echo -e "${YELLOW}⚠️${NC}  reload механизм не явно виден (но это может быть OK)"
    fi
else
    echo -e "${RED}❌${NC} Ошибка в docker-compose конфиге!"
    cat /tmp/compose-config.yaml
    exit 1
fi
echo ""

echo -e "${BLUE}6️⃣  Итоговая проверка${NC}"
echo "─────────────────────────────────────────────"
echo -e "${GREEN}✅${NC} Все проверки пройдены!"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "1. Запусти: docker compose up"
echo "2. Открой: http://localhost:8000 (admin) или http://localhost:8001 (site)"
echo "3. Начни разрабатывать!"
echo ""
echo -e "${YELLOW}Для деталей:${NC}"
echo "- DEVELOPMENT.md — как использовать"
echo "- DOCKER_ANALYSIS.md — как это работает"
echo "- DOCKER_QUICK_REFERENCE.md — частые команды"
echo ""
echo -e "${GREEN}🎉 Всё готово для локальной разработки!${NC}"
