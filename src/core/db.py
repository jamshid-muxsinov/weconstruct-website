import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings

log = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def create_db_and_tables():
    log.info("Creating database and tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database and tables created successfully.")

async def check_db_connection():
    try:
        async with engine.connect() as conn:
            log.info("Database connection successful.")
            return True
    except Exception as e:
        log.error(f"Database connection failed: {e}")
        return False