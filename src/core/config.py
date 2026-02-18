from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "WeConstruct CRM"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO" 
    CORS_ORIGINS: List[str] = []

    DATABASE_URL: str

    GOOGLE_CREDENTIALS_FILE: Optional[str] = None
    GOOGLE_SHEET_WEBHOOK_SECRET: Optional[str] = None
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200

    FIRST_SUPERUSER: Optional[str] = None
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None
    
    REDIS_URL: Optional[str] = "redis://redis:6379/0"
    REDIS_TTL: int = 300
    CACHE_ENABLED: bool = True
     
    ROOT_PATH: str = ""
    COOKIE_SECURE: Optional[bool] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    GOOGLE_WEBHOOK_SECRET_KEY: Optional[str] = None

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value.strip()) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters long.")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
