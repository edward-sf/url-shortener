from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (or .env file locally)."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["local", "test", "production"] = "local"
    database_url: SecretStr
    base_url: str = "http://localhost:8000"
    cleanup_secret: SecretStr

    default_expiry_days: int = Field(default=30, ge=1)
    max_expiry_days: int = Field(default=365, ge=1)
    cleanup_grace_days: int = Field(default=30, ge=0)
    rate_keys_per_hour: int = Field(default=5, ge=1)
    rate_links_per_hour: int = Field(default=60, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Build Settings once per process and reuse it."""
    return Settings()
