"""Environment-driven configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    flywheel_backend: str = "flatfile"
    database_url: str = "postgresql+asyncpg://flywheel:flywheel@localhost:5432/flywheel"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""

    # BYOK encryption (base64-encoded 32-byte AES-256 key)
    encryption_key: str = ""

    # Subsidized API key for anonymous onboarding (~$0.50/trial)
    flywheel_subsidy_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
