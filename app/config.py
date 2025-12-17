"""Configuration management for the Telegram summary app."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    telegram_api_id: int = Field(..., alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(..., alias="TELEGRAM_API_HASH")
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    deepseek_api_key: str = Field(..., alias="DEEPSEEK_API_KEY")

    telegram_session: Optional[str] = Field(
        default=None, alias="TELEGRAM_SESSION", description="Telethon StringSession for user-mode fetch"
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/app.db",
        alias="DATABASE_URL",
    )

    webapp_base_url: str = Field(default="http://localhost:8000", alias="WEBAPP_BASE_URL")
    scheduler_interval_seconds: int = Field(
        default=300, alias="SCHEDULER_INTERVAL_SECONDS"
    )
    initdata_ttl_seconds: int = Field(default=86400, alias="INITDATA_TTL_SECONDS")

    model_config = SettingsConfigDict(
        env_file=Path(".env") if Path(".env").exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()



