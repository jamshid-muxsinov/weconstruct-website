from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
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
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()