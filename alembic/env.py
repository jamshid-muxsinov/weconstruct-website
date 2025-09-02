# alembic/env.py

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# Настройка пути
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

# ВАЖНО: Импортируем ВСЕ модели, чтобы Base.metadata наполнился
from src.models.shop_models import *
from src.core.db import Base

# Конфигурация
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Настройка URL из .env
load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("DATABASE_URL must be set in your .env file")
config.set_main_option('sqlalchemy.url', db_url)

target_metadata = Base.metadata

def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме."""
    # Создаем СИНХРОННЫЙ движок
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()