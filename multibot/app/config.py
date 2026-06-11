from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/multibot"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # Logging
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    NOTIFY_TELEGRAM_CHAT_ID: str = ""

    # URL pública HTTPS del servidor (vacía en desarrollo → se usa polling)
    PUBLIC_BASE_URL: str = ""

    # Admin panel
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-me"

    @field_validator("DATABASE_URL")
    @classmethod
    def ensure_asyncpg(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    def get_database_url(self) -> str:
        return self.DATABASE_URL

    def get_sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
