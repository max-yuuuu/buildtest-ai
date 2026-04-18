from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://buildtest:buildtest@postgres:5432/buildtest"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str | None = None

    app_encryption_key: str = ""

    openai_api_key: str | None = None
    openai_base_url: str | None = None

    upload_max_size_mb: int = 50
    upload_dir: str = "/app/uploads"

    celery_task_always_eager: bool = False

    http_probe_timeout: float = 10.0


settings = Settings()
