from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://ims:imspass@postgres:5432/imsdb"

    # MongoDB
    mongo_url: str = "mongodb://ims:imspass@mongo:27017/imsdb?authSource=admin"
    mongo_db: str = "imsdb"

    # Redis
    redis_url: str = "redis://:imspass@redis:6379/0"

    # JWT
    jwt_secret_key: str = "insecure-dev-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Rate limiting
    rate_limit_signals_per_second: int = 10000
    rate_limit_api_per_minute: int = 1000

    # Ingestion / debounce
    debounce_window_seconds: int = 10
    debounce_max_signals: int = 100
    queue_max_size: int = 50000

    # Observability
    metrics_interval_seconds: int = 5

    # App
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
