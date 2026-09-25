from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OrderFlow Platform"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    service_name: str = "orderflow-api"

    database_url: str = "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow"

    log_level: str = "INFO"

    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.2

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
