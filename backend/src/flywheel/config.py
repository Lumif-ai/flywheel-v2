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

    # Rate limiting
    rate_limit_magic_link: str = "3/hour"
    rate_limit_default: str = "60/minute"

    # Subsidized API key for anonymous onboarding (~$0.50/trial)
    flywheel_subsidy_api_key: str = ""

    # Email (Resend)
    resend_api_key: str = ""  # empty = email disabled, log instead
    email_domain: str = "flywheel.app"  # verified domain in Resend

    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:5173"

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/api/v1/integrations/google-calendar/callback"

    # Google Gmail OAuth (same Google Cloud project, separate scope)
    google_gmail_redirect_uri: str = "http://localhost:5173/api/v1/integrations/gmail/callback"

    # Microsoft Outlook OAuth (Azure AD app registration)
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:5173/api/v1/integrations/outlook/callback"

    # External APIs
    tavily_api_key: str = ""  # empty = web search disabled

    # Production deployment
    environment: str = "development"  # development, staging, production
    sentry_dsn: str = ""  # empty = disabled

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
