"""Environment-driven configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    flywheel_backend: str = "flatfile"
    database_url: str = "postgresql+asyncpg://flywheel:flywheel@localhost:5432/flywheel"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
